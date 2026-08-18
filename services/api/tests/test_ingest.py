"""Ingest fan-out tests: real Pillow thumbnails/EXIF, graceful ML degradation.

The optional CLIP layer is not installed in the verify environment, so these
run against a stubbed ml_clip — the point is that the B2 fan-out (thumbnails +
EXIF sidecar) always works and ML state is reported honestly.
"""

import io

import pytest

from app.repo import asset_store, ml_clip
from app.service import ingest


def _png_bytes(width: int = 32, height: int = 24) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(120, 80, 40)).save(buf, format="PNG")
    return buf.getvalue()


ASSET_ID = "abc123"
ORIGINAL_KEY = f"library/demo/2026/02/{ASSET_ID}.png"


def _ingest_image(store, monkeypatch, *, ml_available: bool):
    store[ORIGINAL_KEY] = _png_bytes()
    monkeypatch.setattr(ml_clip, "is_available", lambda: ml_available)
    if ml_available:
        monkeypatch.setattr(ml_clip, "embed_image", lambda data: [0.1] * ml_clip.EMBED_DIM)
        monkeypatch.setattr(
            ml_clip,
            "zero_shot_tags",
            lambda data, labels, top_k=6: [("a beach", 0.9), ("a sunset", 0.05)],
        )
    return ingest.ingest_asset(
        asset_id=ASSET_ID,
        original_key=ORIGINAL_KEY,
        original_filename="beach.png",
        content_type="image/png",
        size_bytes=len(store[ORIGINAL_KEY]),
        uploaded_at="2026-02-14T00:00:00+00:00",
    )


def test_ingest_writes_thumbnails_and_sidecar_without_ml(fake_asset_store, monkeypatch):
    sidecar = _ingest_image(fake_asset_store, monkeypatch, ml_available=False)

    # Thumbnails always work (Pillow is a core dep).
    for variant in asset_store.THUMBNAIL_VARIANTS:
        key = asset_store.thumb_key(ASSET_ID, variant)
        assert key in fake_asset_store
        assert fake_asset_store[key][:4] == b"RIFF"  # WEBP container
        assert sidecar["derivative_keys"][variant] == key

    assert sidecar["ml_status"] == "unavailable"
    assert "requirements-ml.txt" in sidecar["ml_message"]
    assert sidecar["image_width"] == 32
    assert sidecar["image_height"] == 24
    # No ML artifacts written when the layer is absent.
    assert asset_store.clip_key(ASSET_ID) not in fake_asset_store
    assert asset_store.tags_key(ASSET_ID) not in fake_asset_store
    assert asset_store.sidecar_key(ASSET_ID) in fake_asset_store


def test_ingest_writes_embedding_and_tags_when_ml_present(fake_asset_store, monkeypatch):
    sidecar = _ingest_image(fake_asset_store, monkeypatch, ml_available=True)

    assert sidecar["ml_status"] == "done"
    assert sidecar["embedding_model"] == ml_clip.MODEL_ID
    assert sidecar["embedding_dim"] == ml_clip.EMBED_DIM
    assert sidecar["smart_tags"][0]["label"] == "a beach"

    clip_doc = fake_asset_store[asset_store.clip_key(ASSET_ID)]
    assert b"vector" in clip_doc
    assert asset_store.tags_key(ASSET_ID) in fake_asset_store
    assert sidecar["derivative_keys"]["clip"] == asset_store.clip_key(ASSET_ID)


def test_ingest_video_skips_thumbnails_and_ml(fake_asset_store, monkeypatch):
    key = "library/demo/2026/02/vid1.mp4"
    fake_asset_store[key] = b"\x00\x00\x00\x18ftypmp42fake-body"
    monkeypatch.setattr(ml_clip, "is_available", lambda: True)

    sidecar = ingest.ingest_asset(
        asset_id="vid1",
        original_key=key,
        original_filename="clip.mp4",
        content_type="video/mp4",
        size_bytes=len(fake_asset_store[key]),
        uploaded_at="2026-02-14T00:00:00+00:00",
    )

    assert sidecar["is_image"] is False
    assert sidecar["ml_status"] == "unavailable"
    assert asset_store.thumb_key("vid1", "thumbnail") not in fake_asset_store


def test_ingest_missing_original_raises(fake_asset_store, monkeypatch):
    monkeypatch.setattr(ml_clip, "is_available", lambda: False)
    with pytest.raises(RuntimeError):
        ingest.ingest_asset(
            asset_id="gone",
            original_key="library/demo/2026/02/gone.png",
            original_filename="gone.png",
            content_type="image/png",
            size_bytes=10,
            uploaded_at="2026-02-14T00:00:00+00:00",
        )
