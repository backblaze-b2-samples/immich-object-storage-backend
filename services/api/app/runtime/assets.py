import logging

# Sync `def` handlers: the whole chain is blocking boto3 (and, for re-run,
# blocking CPU inference), so Starlette runs them in its threadpool instead of
# stalling the event loop — same rationale as runtime/files.py.
from fastapi import APIRouter, HTTPException

from app.service import assets as assets_service
from app.service.assets import AssetIdError, AssetNotFoundError
from app.types import (
    AssetActionResponse,
    AssetDetail,
    AssetIdRequest,
    AssetSummary,
    AssetUpdate,
    AssetUpdateRequest,
    LibraryStats,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# SECURITY: these routes are intentionally UNAUTHENTICATED and single-tenant
# (user_id="demo"), matching the file routes — see docs/SECURITY.md. A
# multi-tenant clone must add auth AND scope every asset op to the caller.


def _detail_or_http(asset_id: str) -> AssetDetail:
    try:
        return assets_service.get_asset(asset_id)
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/assets", response_model=list[AssetSummary])
def list_assets_endpoint():
    return assets_service.list_assets()


@router.get("/assets/stats", response_model=LibraryStats)
def library_stats_endpoint():
    return assets_service.get_library_stats()


@router.get("/assets/detail", response_model=AssetDetail)
def asset_detail_endpoint(asset_id: str):
    return _detail_or_http(asset_id)


@router.get("/assets/original-url")
def asset_original_url_endpoint(asset_id: str):
    try:
        return {"url": assets_service.get_original_url(asset_id)}
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.get("/assets/thumbnail-url")
def asset_thumbnail_url_endpoint(asset_id: str, variant: str = "preview"):
    try:
        return {"url": assets_service.get_thumbnail_url(asset_id, variant)}
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.post("/assets/update", response_model=AssetDetail)
def asset_update_endpoint(req: AssetUpdateRequest):
    try:
        update = AssetUpdate(
            description=req.description, favorite=req.favorite, tags=req.tags
        )
        return assets_service.update_asset(req.asset_id, update)
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None


@router.post("/assets/rerun", response_model=AssetDetail)
def asset_rerun_endpoint(req: AssetIdRequest):
    try:
        return assets_service.rerun_ml(req.asset_id)
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except RuntimeError as e:
        logger.warning("Re-run ML failed for %s: %s", req.asset_id, e)
        raise HTTPException(status_code=502, detail="Failed to re-run ML") from None


@router.delete("/assets", response_model=AssetActionResponse)
def asset_delete_endpoint(asset_id: str):
    try:
        assets_service.delete_asset(asset_id)
    except AssetIdError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except AssetNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.detail) from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete asset") from None
    return AssetActionResponse(asset_id=asset_id, deleted=True)
