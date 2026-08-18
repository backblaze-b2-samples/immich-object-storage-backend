"""Asset (photo) lifecycle over the B2 object store.

There is no database: the library is reconstructed by listing ``sidecar/`` and
reading each JSON. Every mutation rewrites the sidecar (and, for re-run, the
ML/thumbnail derivatives); delete cascades across all of an asset's prefixes.
"""

import logging
from datetime import UTC, datetime

from app.repo import asset_store, get_presigned_url
from app.service import ingest
from app.types import AssetDetail, AssetSummary, AssetUpdate, LibraryStats, SmartTag
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)

_SIDECAR_SUFFIX = ".json"
_VALID_ASSET_ID = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)
# Which top-level prefix each stored byte belongs to, for the dashboard's
# storage-by-prefix + write-amplification breakdown.
_PREFIX_BUCKETS = {
    "library/": "originals",
    "thumbs/": "thumbnails",
    "ml/": "ml",
    "sidecar/": "sidecars",
}


class AssetNotFoundError(Exception):
    def __init__(self, asset_id: str):
        self.detail = f"Asset not found: {asset_id}"
        super().__init__(self.detail)


class AssetIdError(Exception):
    def __init__(self, detail: str = "Invalid asset id"):
        self.detail = detail
        super().__init__(detail)


def _validate_asset_id(asset_id: str) -> None:
    if not asset_id or not set(asset_id) <= _VALID_ASSET_ID:
        raise AssetIdError()


def _summary_from_sidecar(sidecar: dict) -> AssetSummary:
    size = int(sidecar.get("size_bytes", 0))
    keys = sidecar.get("derivative_keys", {})
    return AssetSummary(
        asset_id=sidecar["asset_id"],
        original_filename=sidecar.get("original_filename", sidecar["asset_id"]),
        content_type=sidecar.get("content_type", "application/octet-stream"),
        size_bytes=size,
        size_human=humanize_bytes(size),
        uploaded_at=sidecar.get("uploaded_at") or datetime.now(UTC),
        favorite=bool(sidecar.get("favorite", False)),
        tags=list(sidecar.get("tags", [])),
        ml_status=sidecar.get("ml_status", "pending"),
        original_key=sidecar.get("original_key", ""),
        thumbnail_key=keys.get("thumbnail"),
        is_image=bool(sidecar.get("is_image", True)),
    )


def _detail_from_sidecar(sidecar: dict) -> AssetDetail:
    summary = _summary_from_sidecar(sidecar)
    smart_tags = [
        SmartTag(label=t["label"], score=float(t["score"]))
        for t in sidecar.get("smart_tags", [])
        if isinstance(t, dict) and "label" in t and "score" in t
    ]
    return AssetDetail(
        **summary.model_dump(),
        description=sidecar.get("description", ""),
        exif=sidecar.get("exif"),
        image_width=sidecar.get("image_width"),
        image_height=sidecar.get("image_height"),
        smart_tags=smart_tags,
        embedding_model=sidecar.get("embedding_model"),
        embedding_dim=sidecar.get("embedding_dim"),
        ml_message=sidecar.get("ml_message"),
        derivative_keys=sidecar.get("derivative_keys", {}),
    )


def _load_sidecar(asset_id: str) -> dict:
    _validate_asset_id(asset_id)
    sidecar = asset_store.get_json(asset_store.sidecar_key(asset_id))
    if not sidecar:
        raise AssetNotFoundError(asset_id)
    return sidecar


def list_assets() -> list[AssetSummary]:
    """Every asset, newest first, reconstructed from the sidecar prefix."""
    summaries: list[AssetSummary] = []
    for obj in asset_store.list_prefix(asset_store.SIDECAR_PREFIX):
        if not obj["Key"].endswith(_SIDECAR_SUFFIX):
            continue
        sidecar = asset_store.get_json(obj["Key"])
        if sidecar and sidecar.get("asset_id"):
            summaries.append(_summary_from_sidecar(sidecar))
    summaries.sort(key=lambda a: a.uploaded_at, reverse=True)
    return summaries


def get_asset(asset_id: str) -> AssetDetail:
    return _detail_from_sidecar(_load_sidecar(asset_id))


def summary_map() -> dict[str, AssetSummary]:
    """asset_id -> summary, used by search to hydrate ranked ids."""
    return {a.asset_id: a for a in list_assets()}


def update_asset(asset_id: str, update: AssetUpdate) -> AssetDetail:
    """Apply editable metadata (description/favorite/tags) and rewrite sidecar."""
    sidecar = _load_sidecar(asset_id)
    if update.description is not None:
        sidecar["description"] = update.description
    if update.favorite is not None:
        sidecar["favorite"] = bool(update.favorite)
    if update.tags is not None:
        sidecar["tags"] = [t.strip() for t in update.tags if t.strip()]
    asset_store.put_json(asset_store.sidecar_key(asset_id), sidecar)
    logger.info("Asset metadata updated: %s", asset_id)
    return _detail_from_sidecar(sidecar)


def delete_asset(asset_id: str) -> None:
    """Delete the asset and cascade every derivative it owns."""
    sidecar = _load_sidecar(asset_id)
    keys = set(sidecar.get("derivative_keys", {}).values())
    # Defensive: also sweep the whole thumbs/<id>/ and ml/<id>/ prefixes in case
    # a re-run wrote a variant not recorded in this sidecar.
    for prefix in (f"{asset_store.THUMBS_PREFIX}{asset_id}/", f"{asset_store.ML_PREFIX}{asset_id}/"):
        keys.update(obj["Key"] for obj in asset_store.list_prefix(prefix))
    keys.add(asset_store.sidecar_key(asset_id))
    asset_store.delete_keys(sorted(keys))
    logger.info("Asset deleted (cascade): %s (%d objects)", asset_id, len(keys))


def rerun_ml(asset_id: str) -> AssetDetail:
    """Regenerate thumbnails + embedding + smart tags, preserving user edits."""
    sidecar = _load_sidecar(asset_id)
    updated = ingest.ingest_asset(
        asset_id=asset_id,
        original_key=sidecar["original_key"],
        original_filename=sidecar.get("original_filename", asset_id),
        content_type=sidecar.get("content_type", "application/octet-stream"),
        size_bytes=int(sidecar.get("size_bytes", 0)),
        uploaded_at=sidecar.get("uploaded_at") or datetime.now(UTC).isoformat(),
        description=sidecar.get("description", ""),
        favorite=bool(sidecar.get("favorite", False)),
        user_tags=list(sidecar.get("tags", [])),
    )
    return _detail_from_sidecar(updated)


def get_original_url(asset_id: str) -> str:
    sidecar = _load_sidecar(asset_id)
    return get_presigned_url(
        sidecar["original_key"],
        filename=sidecar.get("original_filename"),
        disposition="inline",
    )


def get_thumbnail_url(asset_id: str, variant: str = "preview") -> str:
    if variant not in asset_store.THUMBNAIL_VARIANTS:
        raise AssetIdError(f"Unknown thumbnail variant: {variant}")
    sidecar = _load_sidecar(asset_id)
    key = sidecar.get("derivative_keys", {}).get(variant)
    if not key:
        raise AssetNotFoundError(f"{asset_id}/{variant}")
    return get_presigned_url(key, disposition="inline")


def get_library_stats() -> LibraryStats:
    """Aggregate dashboard metrics + the write-amplification headline."""
    by_bucket: dict[str, int] = {name: 0 for name in _PREFIX_BUCKETS.values()}
    for prefix, bucket in _PREFIX_BUCKETS.items():
        for obj in asset_store.list_prefix(prefix):
            by_bucket[bucket] += int(obj.get("Size", 0))

    original_bytes = by_bucket["originals"]
    derivative_bytes = by_bucket["thumbnails"] + by_bucket["ml"] + by_bucket["sidecars"]
    total_bytes = original_bytes + derivative_bytes

    ml_counts: dict[str, int] = {}
    favorites = 0
    total_assets = 0
    for obj in asset_store.list_prefix(asset_store.SIDECAR_PREFIX):
        if not obj["Key"].endswith(_SIDECAR_SUFFIX):
            continue
        sidecar = asset_store.get_json(obj["Key"])
        if not sidecar or not sidecar.get("asset_id"):
            continue
        total_assets += 1
        status = sidecar.get("ml_status", "pending")
        ml_counts[status] = ml_counts.get(status, 0) + 1
        if sidecar.get("favorite"):
            favorites += 1

    amplification = round(total_bytes / original_bytes, 2) if original_bytes else 0.0
    return LibraryStats(
        total_assets=total_assets,
        original_bytes=original_bytes,
        derivative_bytes=derivative_bytes,
        total_bytes=total_bytes,
        original_human=humanize_bytes(original_bytes),
        derivative_human=humanize_bytes(derivative_bytes),
        total_human=humanize_bytes(total_bytes),
        write_amplification=amplification,
        storage_by_prefix=by_bucket,
        ml_status_counts=ml_counts,
        favorites=favorites,
    )
