<!-- last_verified: 2026-08-18 -->
# Feature: ML Pipeline (ingest fan-out + optional CLIP)

## Purpose
Turn one uploaded original into a set of B2 objects — thumbnails, an EXIF sidecar, and (optionally) a CLIP embedding and smart tags — mirroring how Immich's separate ML container enriches a photo library.

## Used By
- API: runs inside `POST /upload/verify` (ingest) and `POST /assets/rerun` (re-run)
- UI: `/upload` (create) and the asset-detail "Re-run ML processing" action

## Core Functions
- `services/api/app/service/ingest.py` — `ingest_asset()`, thumbnails (Pillow), EXIF, `_run_ml()`, sidecar write
- `services/api/app/repo/ml_clip.py` — lazy OpenCLIP adapter (device autodetect, MPS fallback)
- `services/api/app/repo/asset_store.py` — writes every derivative to B2
- `services/api/requirements-ml.txt` — the optional torch + open-clip-torch layer

## Canonical Files
- Fan-out pipeline: `services/api/app/service/ingest.py`
- Engine adapter: `services/api/app/repo/ml_clip.py`

## Optional-ML packaging (mirrors Immich)
The engine is **real OpenCLIP** (`open-clip-torch`, `ViT-B-32`/`openai`), packaged as a **separately-installed layer** (`requirements-ml.txt`) kept out of the locked core (`requirements.txt` / `requirements.lock`). This mirrors Immich's optional `immich-machine-learning` container, keeps `pnpm verify` green without a ~300 MB torch install, and contains native-ML crashes. torch and `open_clip` are **lazy-imported inside adapter functions**, never at module top level, so `pytest` and plain import succeed with the stack absent.

## Device selection
CPU by default; autodetect **CUDA → Apple MPS → CPU**, overridable with `ML_DEVICE`. torch's MPS backend is young: if a forward pass raises on MPS, the adapter falls back to CPU and caches that (`_demote_to_cpu`), so a bad MPS build never crashes ingest.

## Graceful degradation
`ml_status` is always reported honestly:
- `done` — embedding + tags computed and stored
- `pending` — ingested, ML not yet run
- `failed` — deps present but inference raised
- `unavailable` — ML deps not installed (or the asset is a video)

When ML is unavailable/failed, the asset is still fully ingested and browsable — only search and tags are missing.

## Flow
- Download the original from B2.
- Images: render `thumbnail`/`preview`/`fullsize` WEBP → `thumbs/<id>/`; extract EXIF + dimensions.
- If ML available: `embed_image()` → `ml/<id>/clip.json`; `zero_shot_tags()` → `ml/<id>/tags.json`.
- Write `sidecar/<id>.json` (source of truth) and invalidate the full-bucket listing cache.

## Edge Cases
- Original missing in B2 → `RuntimeError` (genuine storage failure).
- Undecodable image → thumbnails skipped (logged), asset still ingested with an EXIF-less sidecar.
- Video original → thumbnails + ML skipped; `ml_status:"unavailable"`.

## Scoped-out extension: face recognition
Face recognition is documented but **omitted**. Immich uses InsightFace `buffalo_l` (ONNX); it is left out here to keep a single reliable on-device engine and avoid onnxruntime macOS crashes. The `ml/<id>/` prefix reserves room for a future `faces.json`.

## Verification
- Test files: `services/api/tests/test_ingest.py`, `services/api/tests/test_upload_validation.py`
- Required cases: thumbnails+sidecar without ML, embedding+tags with ML, video skip, missing-original error, verify→ingest wiring
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_ingest.py`
- Default pre-PR verify command: `pnpm verify` (ML layer NOT installed)
- Pass criteria: focused tests and `pnpm verify` green with the ML layer absent

## Related Docs
- [Photo library](photo-library.md)
- [Semantic search](semantic-search.md)
- [docs/verification.md](../verification.md)
