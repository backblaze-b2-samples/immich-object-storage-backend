"""Unit + integration tests for photo-upload validation and ingest wiring."""

import re
from datetime import UTC, datetime

import pytest

from app.service import upload as upload_service
from app.service.upload import (
    ALLOWED_TYPES,
    LIBRARY_PREFIX,
    UploadError,
    _validate_declared,
    asset_id_from_key,
    content_type_has_signature,
    create_presigned_upload,
    matches_content_signature,
    mint_asset_key,
    sanitize_filename,
    validate_extension_matches_type,
    verify_upload,
)
from app.types import FileMetadata

_LIBRARY_KEY_RE = re.compile(
    r"^library/demo/\d{4}/\d{2}/[0-9a-f]{32}\.(jpg|png|gif|webp|mp4|mov|webm)$"
)


def _meta(key: str, *, size_bytes: int, content_type: str) -> FileMetadata:
    filename = key.rsplit("/", 1)[-1]
    return FileMetadata(
        key=key,
        filename=filename,
        folder=key[: -len(filename)],
        size_bytes=size_bytes,
        size_human=f"{size_bytes} B",
        content_type=content_type,
        uploaded_at=datetime(2026, 2, 14, tzinfo=UTC),
        url=None,
    )


# --- sanitize_filename ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("a\x00b.txt", "ab.txt"),
        ("my file.txt", "my_file.txt"),
        ("...hidden", "_hidden"),
        ("", "unnamed"),
        ("/", "unnamed"),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["a" * 300 + ".txt", "a" * 300, "a" * 300 + "." + "b" * 250],
)
def test_sanitize_filename_truncates_long_names(raw):
    result = sanitize_filename(raw)
    assert len(result) <= 200
    assert not result.startswith(".")


# --- validate_extension_matches_type (photo/video allow-list) ---------------


@pytest.mark.parametrize(
    ("filename", "content_type", "expected"),
    [
        ("photo.jpg", "image/jpeg", True),
        ("photo.jpeg", "image/jpeg", True),
        ("photo.png", "image/jpeg", False),
        ("noext", "image/jpeg", True),
        ("x.exe", "image/jpeg", False),
        ("notes.md", "text/markdown", False),  # no longer an allowed type
        ("clip.mov", "video/quicktime", True),
        ("clip.mp4", "video/mp4", True),
        ("clip.webm", "video/webm", True),
        ("clip.mp4", "video/quicktime", False),
    ],
)
def test_validate_extension_matches_type(filename, content_type, expected):
    assert validate_extension_matches_type(filename, content_type) is expected


# --- matches_content_signature ----------------------------------------------

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8


@pytest.mark.parametrize(
    ("data", "content_type", "expected"),
    [
        (_PNG, "image/png", True),
        (b"<html>not a png", "image/png", False),
        (_JPEG, "image/jpeg", True),
        (_MP4, "video/mp4", True),
        (b"not-an-mp4-box", "video/mp4", False),
        (b"anything", "video/quicktime", True),  # no signature → accepted
        (b"anything", "video/webm", True),
    ],
)
def test_matches_content_signature(data, content_type, expected):
    assert matches_content_signature(data, content_type) is expected


def test_signature_predicate_agrees_with_checker():
    for ct in ALLOWED_TYPES:
        if content_type_has_signature(ct):
            assert matches_content_signature(b"\x00" * 16, ct) is False
        else:
            assert matches_content_signature(b"\x00" * 16, ct) is True


# --- presign-time declared-upload validation --------------------------------


def test_presign_rejects_oversized(monkeypatch):
    monkeypatch.setattr(upload_service.settings, "max_file_size", 10)
    with pytest.raises(UploadError) as exc:
        _validate_declared("a.jpg", "image/jpeg", 999)
    assert exc.value.status_code == 413


def test_presign_rejects_disallowed_type():
    with pytest.raises(UploadError) as exc:
        _validate_declared("a.txt", "text/plain", 4)
    assert exc.value.status_code == 415


def test_presign_rejects_extension_mismatch():
    with pytest.raises(UploadError) as exc:
        _validate_declared("a.png", "image/jpeg", 4)
    assert exc.value.status_code == 415


def test_presign_rejects_empty_file():
    with pytest.raises(UploadError):
        _validate_declared("a.jpg", "image/jpeg", 0)


# --- library key minting ----------------------------------------------------


def test_mint_asset_key_shape_and_roundtrip():
    asset_id, key = mint_asset_key("image/jpeg")
    assert key.startswith(LIBRARY_PREFIX)
    assert _LIBRARY_KEY_RE.match(key)
    assert asset_id_from_key(key) == asset_id


def test_mint_asset_key_is_unique_per_call():
    keys = {mint_asset_key("image/png")[1] for _ in range(5)}
    assert len(keys) == 5


def test_presign_returns_signed_put_for_photo(monkeypatch):
    captured = {}

    def fake_sign(key, content_type, content_length, expires_in):
        captured.update(
            key=key, content_type=content_type, content_length=content_length
        )
        return "https://b2.example/signed-put"

    monkeypatch.setattr(upload_service, "generate_presigned_upload", fake_sign)
    result = create_presigned_upload("My Photo.png", "image/png", 1234)

    assert _LIBRARY_KEY_RE.match(result.key)
    assert result.asset_id == asset_id_from_key(result.key)
    assert result.url == "https://b2.example/signed-put"
    assert result.headers["Content-Type"] == "image/png"
    assert captured["content_length"] == 1234
    assert captured["content_type"] == "image/png"


@pytest.mark.parametrize(
    ("filename", "content_type"),
    [
        ("beach.jpg", "image/jpeg"),
        ("logo.png", "image/png"),
        ("loop.gif", "image/gif"),
        ("shot.webp", "image/webp"),
        ("clip.mp4", "video/mp4"),
        ("clip.mov", "video/quicktime"),
        ("clip.webm", "video/webm"),
    ],
)
def test_presign_accepts_photo_and_video_types(filename, content_type):
    _validate_declared(filename, content_type, 16)  # must not raise


# --- post-upload verification + ingest fan-out ------------------------------

_PNG_HEAD = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
_KEY = "library/demo/2026/02/" + "a" * 32 + ".png"


def _wire_verify(monkeypatch, *, metadata, head_bytes):
    deleted: list[list[str]] = []
    invalidated: list[bool] = []
    ingested: list[dict] = []
    monkeypatch.setattr(upload_service, "get_file_metadata", lambda key: metadata)
    monkeypatch.setattr(
        upload_service, "get_object_head_bytes", lambda key, length: head_bytes
    )
    monkeypatch.setattr(
        upload_service.asset_store, "delete_keys", lambda keys: deleted.append(keys)
    )
    monkeypatch.setattr(
        upload_service, "invalidate_listing", lambda: invalidated.append(True)
    )
    monkeypatch.setattr(
        upload_service.ingest,
        "ingest_asset",
        lambda **kwargs: ingested.append(kwargs) or {"asset_id": kwargs["asset_id"]},
    )
    return deleted, invalidated, ingested


def test_verify_accepts_and_ingests_valid_object(monkeypatch):
    meta = _meta(_KEY, size_bytes=16, content_type="image/png")
    deleted, invalidated, ingested = _wire_verify(
        monkeypatch, metadata=meta, head_bytes=_PNG_HEAD
    )
    result = verify_upload(_KEY, "My Photo.png")
    assert result.key == _KEY
    assert result.filename == "My_Photo.png"
    assert deleted == []
    assert invalidated == [True]
    assert len(ingested) == 1
    assert ingested[0]["original_key"] == _KEY
    assert ingested[0]["asset_id"] == "a" * 32


def test_verify_rejects_and_deletes_signature_mismatch(monkeypatch):
    meta = _meta(_KEY, size_bytes=16, content_type="image/png")
    deleted, _, ingested = _wire_verify(
        monkeypatch, metadata=meta, head_bytes=b"<html>not a png"
    )
    with pytest.raises(UploadError) as exc:
        verify_upload(_KEY)
    assert exc.value.status_code == 415
    assert deleted == [[_KEY]]
    assert ingested == []


def test_verify_rejects_oversize(monkeypatch):
    monkeypatch.setattr(upload_service.settings, "max_file_size", 10)
    key = "library/demo/2026/02/" + "b" * 32 + ".jpg"
    meta = _meta(key, size_bytes=999, content_type="image/jpeg")
    deleted, _, _ = _wire_verify(monkeypatch, metadata=meta, head_bytes=b"x")
    with pytest.raises(UploadError) as exc:
        verify_upload(key)
    assert exc.value.status_code == 413
    assert deleted == [[key]]


def test_verify_missing_object_is_404(monkeypatch):
    key = "library/demo/2026/02/" + "c" * 32 + ".jpg"
    deleted, _, _ = _wire_verify(monkeypatch, metadata=None, head_bytes=b"")
    with pytest.raises(UploadError) as exc:
        verify_upload(key)
    assert exc.value.status_code == 404
    assert deleted == []


def test_verify_rejects_key_outside_library_prefix():
    with pytest.raises(UploadError):
        verify_upload("other/evil.png")


def test_verify_skips_range_get_for_signatureless_type(monkeypatch):
    key = "library/demo/2026/02/" + "d" * 32 + ".mov"
    meta = _meta(key, size_bytes=12, content_type="video/quicktime")
    fetched: list[int] = []
    monkeypatch.setattr(upload_service, "get_file_metadata", lambda k: meta)
    monkeypatch.setattr(
        upload_service,
        "get_object_head_bytes",
        lambda k, length: fetched.append(length) or b"",
    )
    monkeypatch.setattr(upload_service.asset_store, "delete_keys", lambda keys: None)
    monkeypatch.setattr(upload_service, "invalidate_listing", lambda: None)
    monkeypatch.setattr(
        upload_service.ingest, "ingest_asset", lambda **kwargs: {"asset_id": "x"}
    )

    result = verify_upload(key)
    assert result.key == key
    assert fetched == []  # no wasted Range-GET for a signatureless type


@pytest.mark.asyncio
async def test_successful_verify_increments_uploads_metric(client, monkeypatch):
    from app.runtime import metrics

    monkeypatch.setattr(metrics, "_upload_count", 0)
    key = "library/demo/2026/02/" + "e" * 32 + ".png"
    meta = _meta(key, size_bytes=5, content_type="image/png")
    _wire_verify(monkeypatch, metadata=meta, head_bytes=_PNG_HEAD)

    resp = await client.post("/upload/verify", json={"key": key})
    assert resp.status_code == 200

    metrics_resp = await client.get("/metrics")
    assert "uploads_total 1" in metrics_resp.text
