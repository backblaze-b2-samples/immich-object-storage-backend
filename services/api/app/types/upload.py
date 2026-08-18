from datetime import datetime

from pydantic import BaseModel

from app.types.files import FileMetadataDetail


class FileUploadResponse(BaseModel):
    key: str
    filename: str
    size_bytes: int
    size_human: str
    content_type: str
    uploaded_at: datetime
    url: str | None = None
    metadata: FileMetadataDetail | None = None


class PresignUploadRequest(BaseModel):
    """What the browser declares before uploading directly to B2."""

    filename: str
    content_type: str
    size_bytes: int


class PresignUploadResponse(BaseModel):
    """A short-lived presigned PUT the browser uploads to, plus the exact
    headers it must send. `Content-Length` and `content-type` are signed into
    the URL, so B2 rejects a body of any other size or type.

    `key` is a minted `library/<user>/<YYYY>/<MM>/<asset_id>.<ext>` path;
    `asset_id` is the stable id every derivative and the sidecar share.
    """

    key: str
    asset_id: str
    url: str
    method: str
    content_type: str
    headers: dict[str, str]
    expires_in: int


class VerifyUploadRequest(BaseModel):
    """Sent after the direct PUT so the API can inspect the stored object.

    `original_filename` is the name the user picked (the minted key is opaque),
    preserved in the sidecar for display.
    """

    key: str
    original_filename: str | None = None
