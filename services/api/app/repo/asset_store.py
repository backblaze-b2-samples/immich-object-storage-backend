"""Structured-prefix object store for the photo library.

B2 is the source of truth. Every asset owns objects under Immich-style
prefixes; this module is the only place that reads/writes them, keeping boto3
confined to ``repo/`` (see AGENTS.md). The cached, custom-UA S3 client is
reused from ``b2_client`` so all traffic carries one identity.

Layout::

    library/<user>/<YYYY>/<MM>/<asset_id>.<ext>   original photo
    thumbs/<asset_id>/thumbnail.webp|preview.webp|fullsize.webp
    ml/<asset_id>/clip.json                       {model, dim, vector:[...]}
    ml/<asset_id>/tags.json                       {model, tags:[{label,score}]}
    sidecar/<asset_id>.json                       per-asset source of truth
"""

import json

from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings
from app.repo.b2_client import get_s3_client
from app.repo.list_cache import invalidate as _invalidate_list_cache

USER_ID = "demo"  # single-tenant demo stance (see docs/SECURITY.md)

LIBRARY_PREFIX = "library/"
THUMBS_PREFIX = "thumbs/"
ML_PREFIX = "ml/"
SIDECAR_PREFIX = "sidecar/"

THUMBNAIL_VARIANTS = ("thumbnail", "preview", "fullsize")


def sidecar_key(asset_id: str) -> str:
    return f"{SIDECAR_PREFIX}{asset_id}.json"


def thumb_key(asset_id: str, variant: str) -> str:
    return f"{THUMBS_PREFIX}{asset_id}/{variant}.webp"


def clip_key(asset_id: str) -> str:
    return f"{ML_PREFIX}{asset_id}/clip.json"


def tags_key(asset_id: str) -> str:
    return f"{ML_PREFIX}{asset_id}/tags.json"


def put_bytes(key: str, data: bytes, content_type: str) -> None:
    """Write raw bytes to B2. Raises RuntimeError on failure."""
    client = get_s3_client()
    try:
        client.put_object(
            Bucket=settings.b2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e


def put_json(key: str, obj: dict) -> None:
    """Serialize `obj` to JSON and write it to B2. Raises RuntimeError."""
    payload = json.dumps(obj, separators=(",", ":"), default=str).encode("utf-8")
    put_bytes(key, payload, "application/json")


def get_bytes(key: str) -> bytes | None:
    """Download an object body. Returns None if the object is missing."""
    client = get_s3_client()
    try:
        response = client.get_object(Bucket=settings.b2_bucket_name, Key=key)
        return response["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e


def get_json(key: str) -> dict | None:
    """Read + parse a JSON object. Returns None if missing or unparseable."""
    data = get_bytes(key)
    if data is None:
        return None
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError):
        return None


def list_prefix(prefix: str) -> list[dict]:
    """Every object under `prefix` as raw {Key, Size, LastModified} dicts.

    Paginates fully. Raises RuntimeError on S3 failure.
    """
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {
        "Bucket": settings.b2_bucket_name,
        "Prefix": prefix,
        "MaxKeys": 1000,
    }
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e
    return contents


def delete_keys(keys: list[str]) -> None:
    """Delete a batch of keys (cascade delete). Raises RuntimeError on failure.

    Empty input is a no-op. Invalidates the shared listing cache so the deleted
    objects vanish from the full-bucket explorer and dashboard immediately.
    """
    keys = [k for k in keys if k]
    if not keys:
        return
    client = get_s3_client()
    try:
        # delete_objects caps at 1000 keys per call; an asset never approaches
        # that, but chunk defensively so a future batch delete stays correct.
        for start in range(0, len(keys), 1000):
            chunk = keys[start : start + 1000]
            client.delete_objects(
                Bucket=settings.b2_bucket_name,
                Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
            )
    except (ClientError, BotoCoreError) as e:
        raise RuntimeError(f"B2 batch delete failed: {e}") from e
    _invalidate_list_cache()


def invalidate_listing() -> None:
    """Drop the shared full-bucket listing cache after a write fan-out."""
    _invalidate_list_cache()
