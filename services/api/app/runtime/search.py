import logging

from fastapi import APIRouter, HTTPException

from app.service import search as search_service
from app.types import SearchResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
def search_endpoint(q: str, limit: int = 24):
    """CLIP semantic search over embeddings stored in B2.

    Sync `def` so the blocking B2 embedding load + CPU text-encode run in
    Starlette's threadpool, not on the event loop.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    try:
        return search_service.search(q, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
