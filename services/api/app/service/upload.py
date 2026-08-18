import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import NoReturn

from app.config import settings
from app.repo import (
    asset_store,
    generate_presigned_upload,
    get_file_metadata,
    get_object_head_bytes,
    invalidate_listing,
)
from app.service import ingest
from app.service.files import FileKeyError, validate_key
from app.types import FileUploadResponse, PresignUploadResponse
from app.types.formatting import humanize_bytes

# Photo library: the upload surface accepts images and video only. Everything
# else a bucket might hold is still browsable in the full-bucket /files
# explorer, but the "Add photos" flow mints structured library/ keys and fans
# out photo derivatives, so it constrains what it ingests.
#
# image/svg+xml is deliberately excluded (SVGs can embed <script> → stored XSS
# when served from a public bucket URL).
ALLOWED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Video originals are stored first-class; their derivatives are a documented
    # extension (needs ffmpeg) — see docs/features/ml-pipeline.md.
    "video/mp4",
    "video/quicktime",
    "video/webm",
}

MIME_EXTENSION_MAP: dict[str, set[str]] = {
    "image/jpeg": {"jpg", "jpeg", "jfif"},
    "image/png": {"png"},
    "image/gif": {"gif"},
    "image/webp": {"webp"},
    "video/mp4": {"mp4"},
    "video/quicktime": {"mov"},
    "video/webm": {"webm"},
}

# Canonical extension per type, used to mint a clean library key regardless of
# how the user named the file (the real name is preserved in the sidecar).
_CANONICAL_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}

# Magic-byte signatures for the binary types we accept. The client-declared
# content_type is untrusted, so we sniff the leading bytes and reject obvious
# mismatches. Types without a reliable leading signature (e.g. quicktime/webm)
# are intentionally absent and skip this check.
_CONTENT_SIGNATURES: dict[str, Callable[[bytes], bool]] = {
    "image/jpeg": lambda d: d[:3] == b"\xff\xd8\xff",
    "image/png": lambda d: d[:8] == b"\x89PNG\r\n\x1a\n",
    "image/gif": lambda d: d[:6] in (b"GIF87a", b"GIF89a"),
    "image/webp": lambda d: d[:4] == b"RIFF" and d[8:12] == b"WEBP",
    "video/mp4": lambda d: d[4:8] == b"ftyp",  # ISO base media 'ftyp' box
}


def content_type_has_signature(content_type: str) -> bool:
    """True if `content_type` has a magic-byte signature worth sniffing."""
    return content_type in _CONTENT_SIGNATURES


def matches_content_signature(data: bytes, content_type: str) -> bool:
    """Return True if `data`'s leading bytes are consistent with `content_type`.

    Types without a known signature return True (nothing to verify).
    """
    check = _CONTENT_SIGNATURES.get(content_type)
    return check(data) if check else True


_SAFE_FILENAME_RE = re.compile(r"[^\w\-.]")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename: strip path components, remove unsafe chars, limit length."""
    name = filename.replace("\\", "/").split("/")[-1]
    name = name.replace("\x00", "")
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = re.sub(r"[_.]{2,}", "_", name)
    name = name.lstrip(".").strip()
    if len(name) > 200:
        base, sep, ext = name.rpartition(".")
        name = (
            base[: 200 - len(ext) - 1] + "." + ext
            if sep and len(ext) < 200
            else name[:200]
        )
    return name or "unnamed"


def validate_extension_matches_type(filename: str, content_type: str) -> bool:
    """Verify the file extension is consistent with the declared MIME type."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed_exts = MIME_EXTENSION_MAP.get(content_type)
    if allowed_exts is None:
        return False
    if not ext:
        return True
    return ext in allowed_exts


class UploadError(Exception):
    """Raised when upload validation fails."""

    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Single-tenant demo: every original lands under this prefix (see
# docs/SECURITY.md). B2 remains the source of truth — the library is
# reconstructed from sidecars, not the object keys.
USER_ID = "demo"
LIBRARY_PREFIX = f"library/{USER_ID}/"
# Leading bytes fetched for the post-upload sniff.
_SNIFF_BYTES = 512


def _validate_declared(filename: str, content_type: str, size_bytes: int) -> None:
    """Validate a *declared* upload (pre-bytes). Raises UploadError on failure."""
    if not filename:
        raise UploadError("No filename provided")
    if size_bytes <= 0:
        raise UploadError("Empty file")
    if size_bytes > settings.max_file_size:
        raise UploadError(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            status_code=413,
        )
    if content_type not in ALLOWED_TYPES:
        raise UploadError(
            f"File type '{content_type}' not allowed. Upload a photo "
            "(JPEG/PNG/GIF/WEBP) or video (MP4/MOV/WEBM).",
            status_code=415,
        )
    safe_name = sanitize_filename(filename)
    if not validate_extension_matches_type(safe_name, content_type):
        raise UploadError(
            "File extension does not match declared content type",
            status_code=415,
        )


def mint_asset_key(content_type: str) -> tuple[str, str]:
    """Return a fresh (asset_id, library key) under library/<user>/<YYYY>/<MM>/."""
    asset_id = uuid.uuid4().hex
    ext = _CANONICAL_EXT.get(content_type, "bin")
    now = datetime.now(UTC)
    key = f"{LIBRARY_PREFIX}{now:%Y}/{now:%m}/{asset_id}.{ext}"
    return asset_id, key


def asset_id_from_key(key: str) -> str:
    """Recover the asset id from a minted library key."""
    return key.rsplit("/", 1)[-1].rsplit(".", 1)[0]


def create_presigned_upload(
    filename: str, content_type: str, size_bytes: int
) -> PresignUploadResponse:
    """Validate a declared photo upload and return a presigned PUT for direct-to-B2.

    `size_bytes` and `content_type` are signed into the URL, so B2 refuses any
    body of a different size or type. Raises UploadError on failure.
    """
    _validate_declared(filename, content_type, size_bytes)
    asset_id, key = mint_asset_key(content_type)
    expires_in = settings.presign_upload_expiry_seconds
    url = generate_presigned_upload(key, content_type, size_bytes, expires_in)
    return PresignUploadResponse(
        key=key,
        asset_id=asset_id,
        url=url,
        method="PUT",
        content_type=content_type,
        headers={"Content-Type": content_type},
        expires_in=expires_in,
    )


def verify_upload(key: str, original_filename: str | None = None) -> FileUploadResponse:
    """Inspect a just-uploaded original, then run the ingest fan-out.

    HEAD covers size/type; a Range-GET of the leading bytes recovers the
    magic-byte sniff. Anything invalid is deleted. On success the ingest
    pipeline generates thumbnails + EXIF sidecar + (optional) CLIP embedding and
    smart tags, all written to B2. Raises UploadError on any validation failure.
    """
    if not key.startswith(LIBRARY_PREFIX):
        raise UploadError("Upload key must be under the library/ prefix")
    try:
        validate_key(key)
    except FileKeyError as e:
        raise UploadError(e.detail) from None

    metadata = get_file_metadata(key)  # HEAD
    if not metadata:
        raise UploadError("Uploaded object not found", status_code=404)

    def _reject(detail: str, status_code: int) -> NoReturn:
        asset_store.delete_keys([key])
        raise UploadError(detail, status_code=status_code)

    if metadata.size_bytes == 0:
        _reject("Empty file", 400)
    if metadata.size_bytes > settings.max_file_size:
        _reject(
            f"File too large. Max size: {humanize_bytes(settings.max_file_size)}",
            413,
        )
    if metadata.content_type not in ALLOWED_TYPES:
        _reject(f"File type '{metadata.content_type}' not allowed", 415)
    if not validate_extension_matches_type(metadata.filename, metadata.content_type):
        _reject("File extension does not match declared content type", 415)

    if content_type_has_signature(metadata.content_type):
        head = get_object_head_bytes(key, _SNIFF_BYTES)
        if head is None:
            raise UploadError("Uploaded object not found", status_code=404)
        if not matches_content_signature(head, metadata.content_type):
            _reject("File contents do not match the declared type", 415)

    asset_id = asset_id_from_key(key)
    display_name = sanitize_filename(original_filename) if original_filename else metadata.filename
    ingest.ingest_asset(
        asset_id=asset_id,
        original_key=key,
        original_filename=display_name,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        uploaded_at=metadata.uploaded_at.isoformat(),
    )
    invalidate_listing()
    return FileUploadResponse(
        key=key,
        filename=display_name,
        size_bytes=metadata.size_bytes,
        size_human=metadata.size_human,
        content_type=metadata.content_type,
        uploaded_at=metadata.uploaded_at,
        url=metadata.url,
        metadata=None,
    )
