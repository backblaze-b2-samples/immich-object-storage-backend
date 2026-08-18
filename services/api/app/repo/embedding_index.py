"""Brute-force semantic index over CLIP embeddings loaded from B2.

Every asset's embedding lives at ``ml/<asset_id>/clip.json``. Search loads them
all and cosine-ranks against the query embedding. Cosine is pure Python (no
numpy), so this file carries no ML dependency — it works whenever embeddings
exist, regardless of whether the CLIP layer is installed on this process.

Fine for a demo library. Production would push embeddings into a vector DB
(Immich uses pgvecto.rs); see docs/features/semantic-search.md.
"""

import math

from app.repo import asset_store

_CLIP_SUFFIX = "/clip.json"


def _asset_id_from_clip_key(key: str) -> str | None:
    # ml/<asset_id>/clip.json -> <asset_id>
    if not key.startswith(asset_store.ML_PREFIX) or not key.endswith(_CLIP_SUFFIX):
        return None
    return key[len(asset_store.ML_PREFIX) : -len(_CLIP_SUFFIX)]


def load_all_embeddings() -> dict[str, list[float]]:
    """Map asset_id -> embedding vector for every stored ``clip.json``.

    Raises RuntimeError on an S3 listing failure; skips individual objects that
    are missing or malformed rather than failing the whole search.
    """
    embeddings: dict[str, list[float]] = {}
    for obj in asset_store.list_prefix(asset_store.ML_PREFIX):
        asset_id = _asset_id_from_clip_key(obj["Key"])
        if asset_id is None:
            continue
        doc = asset_store.get_json(obj["Key"])
        if not doc:
            continue
        vector = doc.get("vector")
        if isinstance(vector, list) and vector:
            embeddings[asset_id] = vector
    return embeddings


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def rank(
    query: list[float], embeddings: dict[str, list[float]], top_k: int = 24
) -> list[tuple[str, float]]:
    """Return (asset_id, score) pairs sorted by descending cosine similarity."""
    scored = [
        (asset_id, cosine_similarity(query, vector))
        for asset_id, vector in embeddings.items()
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
