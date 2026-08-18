"""On-device CLIP adapter — the sample's headline engine.

Uses **real OpenCLIP** (`open-clip-torch`), model **ViT-B-32 / openai** — exactly
the library and default model Immich's machine-learning service ships. It is an
OPTIONAL layer (`services/api/requirements-ml.txt`): torch and open_clip are
**lazy-imported inside every function**, never at module top level, so `pytest`
and plain module import succeed with the ML stack absent. When the deps are
missing (or inference raises) the caller degrades gracefully — the asset is
still ingested and served; only smart search/tags report ``unavailable``.

This mirrors Immich's architecture, where ML is a separate, optional
`immich-machine-learning` container.

Device: CPU by default; autodetect CUDA -> Apple MPS -> CPU, with an
`ML_DEVICE` override (see settings). torch's MPS backend is usable but young —
if a forward pass raises on MPS we fall back to CPU and cache that.
"""

import io
import logging
import threading

from app.config import settings

logger = logging.getLogger(__name__)

MODEL_NAME = "ViT-B-32"
PRETRAINED = "openai"
MODEL_ID = f"{MODEL_NAME}/{PRETRAINED}"
EMBED_DIM = 512  # ViT-B-32 image/text projection dim

# Cached (model, preprocess, tokenizer, device) tuple + guard. Populated on
# first use so the ~340 MB weight download / load happens lazily, once.
_STATE: tuple | None = None
_LOCK = threading.Lock()


def is_available() -> bool:
    """True when the optional ML stack (torch + open_clip) can be imported."""
    try:
        import open_clip  # noqa: F401
        import torch  # noqa: F401
    except Exception:
        return False
    return True


def _select_device(torch) -> str:
    override = (settings.ml_device or "").strip().lower()
    if override in ("cpu", "cuda", "mps"):
        return override
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def _load():
    """Load model/transform/tokenizer once and move to the chosen device."""
    global _STATE
    if _STATE is not None:
        return _STATE
    with _LOCK:
        if _STATE is not None:
            return _STATE
        import open_clip
        import torch

        device = _select_device(torch)
        model, _, preprocess = open_clip.create_model_and_transforms(
            MODEL_NAME, pretrained=PRETRAINED
        )
        tokenizer = open_clip.get_tokenizer(MODEL_NAME)
        model.eval()
        try:
            model = model.to(device)
        except Exception:
            logger.warning("Could not move CLIP model to %s; using cpu", device)
            device = "cpu"
            model = model.to("cpu")
        logger.info("CLIP model loaded (%s) on device=%s", MODEL_ID, device)
        _STATE = (model, preprocess, tokenizer, device)
        return _STATE


def _demote_to_cpu():
    """Rebind the cached model onto CPU after an MPS/CUDA forward failure."""
    global _STATE
    if _STATE is None:
        return
    model, preprocess, tokenizer, _ = _STATE
    model = model.to("cpu")
    _STATE = (model, preprocess, tokenizer, "cpu")


def _normalize(vec) -> list[float]:
    import torch

    with torch.no_grad():
        vec = vec / vec.norm(dim=-1, keepdim=True)
    return vec.squeeze(0).tolist()


def embed_image(image_bytes: bytes) -> list[float]:
    """Return the L2-normalized CLIP image embedding for `image_bytes`.

    Raises RuntimeError if the ML stack is unavailable so callers can mark the
    asset ``unavailable``/``failed`` instead of 500-ing.
    """
    if not is_available():
        raise RuntimeError("ML layer not installed (open-clip-torch/torch missing)")
    from PIL import Image

    model, preprocess, _, device = _load()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return _encode_image(model, preprocess, device, img)


def _encode_image(model, preprocess, device, img) -> list[float]:
    import torch

    tensor = preprocess(img).unsqueeze(0)
    try:
        with torch.no_grad():
            features = model.encode_image(tensor.to(device))
    except Exception:
        if device != "cpu":
            logger.warning("CLIP image forward failed on %s; retrying on cpu", device)
            _demote_to_cpu()
            with torch.no_grad():
                features = model.to("cpu").encode_image(tensor.to("cpu"))
        else:
            raise
    return _normalize(features.float())


def embed_text(text: str) -> list[float]:
    """Return the L2-normalized CLIP text embedding for `text`."""
    if not is_available():
        raise RuntimeError("ML layer not installed (open-clip-torch/torch missing)")
    import torch

    model, _, tokenizer, device = _load()
    tokens = tokenizer([text])
    try:
        with torch.no_grad():
            features = model.encode_text(tokens.to(device))
    except Exception:
        if device != "cpu":
            logger.warning("CLIP text forward failed on %s; retrying on cpu", device)
            _demote_to_cpu()
            with torch.no_grad():
                features = model.to("cpu").encode_text(tokens.to("cpu"))
        else:
            raise
    return _normalize(features.float())


def zero_shot_tags(
    image_bytes: bytes, labels: list[str], top_k: int = 6
) -> list[tuple[str, float]]:
    """Zero-shot classify `image_bytes` against `labels` (same CLIP model).

    Returns the top_k (label, probability) pairs, softmax over cosine
    similarity between the image embedding and each label's text embedding.
    """
    if not is_available():
        raise RuntimeError("ML layer not installed (open-clip-torch/torch missing)")
    import torch
    from PIL import Image

    model, preprocess, tokenizer, device = _load()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    prompts = [f"a photo of {label}" for label in labels]

    def _run(dev):
        with torch.no_grad():
            image_features = model.encode_image(preprocess(img).unsqueeze(0).to(dev))
            text_features = model.encode_text(tokenizer(prompts).to(dev))
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            logits = (100.0 * image_features @ text_features.T).softmax(dim=-1)
        return logits.squeeze(0)

    try:
        probs = _run(device)
    except Exception:
        if device != "cpu":
            logger.warning("CLIP zero-shot failed on %s; retrying on cpu", device)
            _demote_to_cpu()
            probs = _run("cpu")
        else:
            raise

    scored = sorted(
        (
            (label, float(prob))
            for label, prob in zip(labels, probs.tolist(), strict=False)
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    return scored[:top_k]
