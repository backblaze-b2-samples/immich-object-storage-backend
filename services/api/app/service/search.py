"""CLIP semantic search: text query -> embedding -> cosine rank over B2.

The query is embedded with the same OpenCLIP model that produced the image
embeddings at ingest, then cosine-ranked against every ``ml/<id>/clip.json``
loaded from B2. When the optional ML layer is absent the search reports
``unavailable`` (and says how to enable it) rather than failing.
"""

import logging

from app.repo import embedding_index, ml_clip
from app.service import assets
from app.types import SearchMatch, SearchResponse

logger = logging.getLogger(__name__)

_UNAVAILABLE_MSG = (
    "Semantic search needs the optional CLIP layer. Install it with "
    "`pip install -r services/api/requirements-ml.txt`, then re-run ML on your "
    "assets so their embeddings exist."
)
_NO_EMBEDDINGS_MSG = (
    "No CLIP embeddings found yet. Upload photos with the ML layer installed, "
    "or open an asset and use “Re-run ML processing”."
)


def search(query: str, limit: int = 24) -> SearchResponse:
    query = query.strip()
    if not query:
        raise ValueError("Query must not be empty")

    if not ml_clip.is_available():
        return SearchResponse(query=query, ml_status="unavailable", message=_UNAVAILABLE_MSG)

    embeddings = embedding_index.load_all_embeddings()
    if not embeddings:
        return SearchResponse(query=query, ml_status="ok", message=_NO_EMBEDDINGS_MSG)

    try:
        query_vec = ml_clip.embed_text(query)
    except Exception as exc:
        # Surface as "unavailable" rather than 500 — search must never crash.
        logger.warning("CLIP text embedding failed: %s", exc, exc_info=True)
        return SearchResponse(
            query=query,
            ml_status="unavailable",
            message=f"CLIP query embedding failed: {exc}",
        )

    ranked = embedding_index.rank(query_vec, embeddings, top_k=limit)
    summaries = assets.summary_map()
    results = [
        SearchMatch(asset=summaries[asset_id], score=round(score, 4))
        for asset_id, score in ranked
        if asset_id in summaries
    ]
    return SearchResponse(query=query, ml_status="ok", results=results)
