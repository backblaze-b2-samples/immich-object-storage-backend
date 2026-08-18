"""Ingest fan-out: one uploaded original becomes many B2 objects.

After a photo's original lands in ``library/`` (presigned PUT + verify), this
runs the derivative pipeline and writes every artifact back to B2:

    thumbnails (Pillow -> WEBP)   -> thumbs/<id>/thumbnail|preview|fullsize.webp
    EXIF + dimensions             -> folded into the sidecar
    CLIP embedding (optional)     -> ml/<id>/clip.json
    zero-shot smart tags (opt.)   -> ml/<id>/tags.json
    sidecar (source of truth)     -> sidecar/<id>.json

Thumbnails + EXIF use Pillow (a core dependency) and always work. The CLIP
steps use the optional ml_clip layer and degrade gracefully — the asset is
still fully ingested and browsable when torch/open_clip are absent.
"""

import io
import logging

from app.repo import asset_store, ml_clip

logger = logging.getLogger(__name__)

# WEBP thumbnail long-edge sizes (Immich ships thumbnail/preview tiers; we add a
# fullsize tier so the detail view has a crisp inline image without serving the
# multi-MB original).
_THUMB_SIZES = {"thumbnail": 256, "preview": 1024, "fullsize": 2048}

# Fixed candidate vocabulary for zero-shot smart tags. ml_clip wraps each as
# "a photo of <label>", so entries are bare subject nouns.
DEFAULT_TAG_LABELS = [
    "a beach",
    "a sunset",
    "mountains",
    "a forest",
    "a city street",
    "food",
    "a dog",
    "a cat",
    "a portrait of a person",
    "a group of people",
    "a flower",
    "a car",
    "snow",
    "a night sky",
    "a document or screenshot",
    "an animal",
]

ML_UNAVAILABLE_MSG = (
    "Optional CLIP layer not installed. Run "
    "`pip install -r services/api/requirements-ml.txt` and re-run ML "
    "(first run downloads the ViT-B-32 weights, ~340 MB)."
)
VIDEO_ML_MSG = (
    "Thumbnails and CLIP run on images. Video derivatives (poster frame, "
    "embedding) are a documented extension that needs ffmpeg."
)


def _generate_thumbnails(image_bytes: bytes) -> dict[str, bytes]:
    """Render WEBP thumbnails at each tier. Raises on undecodable input."""
    from PIL import Image, ImageOps

    out: dict[str, bytes] = {}
    for name, size in _THUMB_SIZES.items():
        img = Image.open(io.BytesIO(image_bytes))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((size, size))
        buf = io.BytesIO()
        img.save(buf, format="WEBP", quality=82, method=4)
        out[name] = buf.getvalue()
    return out


def _extract_image_meta(image_bytes: bytes) -> dict:
    """Width/height + a flattened EXIF dict. Never raises (best-effort)."""
    result: dict = {"image_width": None, "image_height": None, "exif": None}
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS

        img = Image.open(io.BytesIO(image_bytes))
        result["image_width"] = img.width
        result["image_height"] = img.height
        raw = img.getexif()
        if raw:
            exif: dict[str, str] = {}
            for tag_id, value in raw.items():
                tag = TAGS.get(tag_id, tag_id)
                if isinstance(value, bytes):
                    try:
                        value = value.decode("utf-8", errors="replace")
                    except Exception:
                        value = str(value)
                exif[str(tag)] = str(value)
            result["exif"] = exif or None
    except Exception:
        logger.warning("EXIF/dimension extraction failed", exc_info=True)
    return result


def _run_ml(image_bytes: bytes) -> dict:
    """Compute embedding + smart tags. Returns a partial sidecar fragment.

    Degrades to ``unavailable`` (deps absent) or ``failed`` (inference raised)
    without ever propagating an exception — ingest must not 500.
    """
    if not ml_clip.is_available():
        return {"ml_status": "unavailable", "ml_message": ML_UNAVAILABLE_MSG}
    try:
        embedding = ml_clip.embed_image(image_bytes)
        tags = ml_clip.zero_shot_tags(image_bytes, DEFAULT_TAG_LABELS)
        return {
            "ml_status": "done",
            "ml_message": None,
            "embedding": embedding,
            "embedding_model": ml_clip.MODEL_ID,
            "embedding_dim": len(embedding),
            "smart_tags": [{"label": label, "score": score} for label, score in tags],
        }
    except Exception as exc:
        # Report, never crash ingest — the asset must still be stored/browsable.
        logger.warning("CLIP inference failed: %s", exc, exc_info=True)
        return {"ml_status": "failed", "ml_message": f"CLIP inference failed: {exc}"}


def ingest_asset(
    *,
    asset_id: str,
    original_key: str,
    original_filename: str,
    content_type: str,
    size_bytes: int,
    uploaded_at: str,
    description: str = "",
    favorite: bool = False,
    user_tags: list[str] | None = None,
) -> dict:
    """Run the derivative pipeline for one asset and write its sidecar.

    Returns the sidecar dict. Raises RuntimeError only if the original cannot
    be read from B2 (a genuine storage failure). Overwrites existing
    derivatives, so it doubles as the re-run path.
    """
    data = asset_store.get_bytes(original_key)
    if data is None:
        raise RuntimeError(f"Original not found in B2: {original_key}")

    is_image = content_type.startswith("image/")
    derivative_keys: dict[str, str] = {"original": original_key}
    image_meta = {"image_width": None, "image_height": None, "exif": None}
    ml: dict = {"ml_status": "pending", "ml_message": None}

    if is_image:
        try:
            for name, blob in _generate_thumbnails(data).items():
                key = asset_store.thumb_key(asset_id, name)
                asset_store.put_bytes(key, blob, "image/webp")
                derivative_keys[name] = key
        except Exception:
            logger.warning("Thumbnail generation failed for %s", asset_id, exc_info=True)
        image_meta = _extract_image_meta(data)
        ml = _run_ml(data)
        if ml.get("embedding") is not None:
            clip_key = asset_store.clip_key(asset_id)
            asset_store.put_json(
                clip_key,
                {
                    "model": ml["embedding_model"],
                    "dim": ml["embedding_dim"],
                    "vector": ml["embedding"],
                },
            )
            derivative_keys["clip"] = clip_key
        if ml.get("smart_tags"):
            tags_key = asset_store.tags_key(asset_id)
            asset_store.put_json(
                tags_key, {"model": ml.get("embedding_model"), "tags": ml["smart_tags"]}
            )
            derivative_keys["tags"] = tags_key
    else:
        ml = {"ml_status": "unavailable", "ml_message": VIDEO_ML_MSG}

    sidecar_key = asset_store.sidecar_key(asset_id)
    derivative_keys["sidecar"] = sidecar_key
    sidecar = {
        "asset_id": asset_id,
        "original_filename": original_filename,
        "original_key": original_key,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "uploaded_at": uploaded_at,
        "is_image": is_image,
        "description": description,
        "favorite": favorite,
        "tags": user_tags or [],
        "ml_status": ml.get("ml_status", "pending"),
        "ml_message": ml.get("ml_message"),
        "smart_tags": ml.get("smart_tags", []),
        "embedding_model": ml.get("embedding_model"),
        "embedding_dim": ml.get("embedding_dim"),
        "image_width": image_meta["image_width"],
        "image_height": image_meta["image_height"],
        "exif": image_meta["exif"],
        "derivative_keys": derivative_keys,
    }
    asset_store.put_json(sidecar_key, sidecar)
    asset_store.invalidate_listing()
    logger.info(
        "Ingested asset %s (ml_status=%s, derivatives=%d)",
        asset_id,
        sidecar["ml_status"],
        len(derivative_keys),
    )
    return sidecar
