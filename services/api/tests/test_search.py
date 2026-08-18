"""Semantic-search tests: graceful degradation + real cosine ranking."""

import json

from app.repo import asset_store, embedding_index, ml_clip
from app.service import search as search_service


def _seed_asset(store, asset_id, vector):
    original_key = f"library/demo/2026/02/{asset_id}.jpg"
    store[asset_store.clip_key(asset_id)] = json.dumps(
        {"model": "ViT-B-32/openai", "dim": len(vector), "vector": vector}
    ).encode()
    sidecar = {
        "asset_id": asset_id,
        "original_filename": f"{asset_id}.jpg",
        "original_key": original_key,
        "content_type": "image/jpeg",
        "size_bytes": 100,
        "uploaded_at": "2026-02-14T00:00:00+00:00",
        "is_image": True,
        "favorite": False,
        "tags": [],
        "ml_status": "done",
        "smart_tags": [],
        "derivative_keys": {"original": original_key},
    }
    store[asset_store.sidecar_key(asset_id)] = json.dumps(sidecar).encode()


def test_search_unavailable_without_ml(fake_asset_store, monkeypatch):
    monkeypatch.setattr(ml_clip, "is_available", lambda: False)
    resp = search_service.search("beach at sunset")
    assert resp.ml_status == "unavailable"
    assert "requirements-ml.txt" in resp.message
    assert resp.results == []


def test_search_ranks_by_cosine(fake_asset_store, monkeypatch):
    # Two clearly distinct embeddings; the query is aligned with "beach".
    _seed_asset(fake_asset_store, "beach", [1.0, 0.0, 0.0])
    _seed_asset(fake_asset_store, "forest", [0.0, 1.0, 0.0])
    monkeypatch.setattr(ml_clip, "is_available", lambda: True)
    monkeypatch.setattr(ml_clip, "embed_text", lambda q: [0.9, 0.1, 0.0])

    resp = search_service.search("a sunny beach")
    assert resp.ml_status == "ok"
    assert resp.results[0].asset.asset_id == "beach"
    assert resp.results[0].score > resp.results[1].score


def test_search_no_embeddings_message(fake_asset_store, monkeypatch):
    monkeypatch.setattr(ml_clip, "is_available", lambda: True)
    resp = search_service.search("anything")
    assert resp.ml_status == "ok"
    assert "Re-run ML" in resp.message


def test_cosine_similarity_is_pure_python():
    assert embedding_index.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert embedding_index.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert embedding_index.cosine_similarity([], []) == 0.0
