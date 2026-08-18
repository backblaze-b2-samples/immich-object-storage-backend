"""Asset lifecycle tests over the in-memory store: read/edit/delete/run/stats."""

import pytest

from app.repo import asset_store
from app.service import assets as assets_service
from app.service.assets import AssetIdError, AssetNotFoundError
from app.types import AssetUpdate


def _seed_sidecar(store, asset_id="a1", *, favorite=False, ml_status="done"):
    original_key = f"library/demo/2026/02/{asset_id}.jpg"
    store[original_key] = b"\xff\xd8\xff\xe0original-bytes"
    store[asset_store.thumb_key(asset_id, "thumbnail")] = b"RIFFthumb"
    store[asset_store.clip_key(asset_id)] = b'{"vector":[0.1,0.2]}'
    sidecar = {
        "asset_id": asset_id,
        "original_filename": f"{asset_id}.jpg",
        "original_key": original_key,
        "content_type": "image/jpeg",
        "size_bytes": 1024,
        "uploaded_at": "2026-02-14T00:00:00+00:00",
        "is_image": True,
        "description": "",
        "favorite": favorite,
        "tags": [],
        "ml_status": ml_status,
        "ml_message": None,
        "smart_tags": [{"label": "a beach", "score": 0.9}],
        "embedding_model": "ViT-B-32/openai",
        "embedding_dim": 512,
        "image_width": 100,
        "image_height": 80,
        "exif": {"Make": "TestCam"},
        "derivative_keys": {
            "original": original_key,
            "thumbnail": asset_store.thumb_key(asset_id, "thumbnail"),
            "clip": asset_store.clip_key(asset_id),
            "sidecar": asset_store.sidecar_key(asset_id),
        },
    }
    store[asset_store.sidecar_key(asset_id)] = __import__("json").dumps(sidecar).encode()
    return sidecar


def test_list_and_get_asset(fake_asset_store):
    _seed_sidecar(fake_asset_store, "a1")
    _seed_sidecar(fake_asset_store, "a2")

    summaries = assets_service.list_assets()
    assert {s.asset_id for s in summaries} == {"a1", "a2"}

    detail = assets_service.get_asset("a1")
    assert detail.smart_tags[0].label == "a beach"
    assert detail.exif == {"Make": "TestCam"}
    assert detail.thumbnail_key == asset_store.thumb_key("a1", "thumbnail")


def test_get_missing_asset_raises(fake_asset_store):
    with pytest.raises(AssetNotFoundError):
        assets_service.get_asset("nope")


def test_invalid_asset_id_rejected(fake_asset_store):
    with pytest.raises(AssetIdError):
        assets_service.get_asset("../etc/passwd")


def test_update_asset_rewrites_sidecar(fake_asset_store):
    _seed_sidecar(fake_asset_store, "a1")
    detail = assets_service.update_asset(
        "a1", AssetUpdate(description="a day at the beach", favorite=True, tags=["trip", " "])
    )
    assert detail.description == "a day at the beach"
    assert detail.favorite is True
    assert detail.tags == ["trip"]  # blanks dropped

    # Persisted, not just returned.
    again = assets_service.get_asset("a1")
    assert again.favorite is True


def test_delete_asset_cascades(fake_asset_store):
    _seed_sidecar(fake_asset_store, "a1")
    # A stray re-run variant not recorded in derivative_keys must still go.
    fake_asset_store[asset_store.thumb_key("a1", "preview")] = b"RIFFstray"

    assets_service.delete_asset("a1")

    remaining = [k for k in fake_asset_store if "a1" in k]
    assert remaining == []


def test_rerun_ml_preserves_user_edits(fake_asset_store, monkeypatch):
    _seed_sidecar(fake_asset_store, "a1")
    assets_service.update_asset("a1", AssetUpdate(description="keep me", favorite=True))
    # Give ingest a decodable original + stubbed ML.
    import io

    from PIL import Image

    from app.repo import ml_clip

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), (1, 2, 3)).save(buf, format="JPEG")
    fake_asset_store["library/demo/2026/02/a1.jpg"] = buf.getvalue()
    monkeypatch.setattr(ml_clip, "is_available", lambda: False)

    detail = assets_service.rerun_ml("a1")
    assert detail.description == "keep me"
    assert detail.favorite is True
    assert detail.ml_status == "unavailable"


def test_library_stats_reports_amplification(fake_asset_store):
    _seed_sidecar(fake_asset_store, "a1", ml_status="done")
    _seed_sidecar(fake_asset_store, "a2", favorite=True, ml_status="unavailable")

    stats = assets_service.get_library_stats()
    assert stats.total_assets == 2
    assert stats.favorites == 1
    assert stats.ml_status_counts == {"done": 1, "unavailable": 1}
    assert stats.original_bytes > 0
    assert stats.write_amplification >= 1.0
