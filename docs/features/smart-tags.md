<!-- last_verified: 2026-08-18 -->
# Feature: Smart Tags

## Purpose
Automatically label each photo with a handful of subject tags using zero-shot CLIP classification — the same on-device model as search, no training and no labels required.

## Used By
- UI: asset-detail dialog (smart-tag badges); recomputed by "Re-run ML processing"
- API: produced at ingest (`POST /upload/verify`) and re-run (`POST /assets/rerun`); read via `GET /assets/detail`

## Core Functions
- `services/api/app/repo/ml_clip.py` — `zero_shot_tags(image_bytes, labels, top_k)` (real OpenCLIP)
- `services/api/app/service/ingest.py` — `DEFAULT_TAG_LABELS`, `_run_ml()`, writes `ml/<id>/tags.json`
- `services/api/app/types/assets.py` — `SmartTag`

## Canonical Files
- Zero-shot classifier: `services/api/app/repo/ml_clip.py`

## Inputs
- image bytes (the ingested original)
- a fixed candidate label set (`DEFAULT_TAG_LABELS`, e.g. beach, sunset, mountains, a dog, food, …)

## Outputs
- `ml/<asset_id>/tags.json` = `{model, tags:[{label, score}]}`
- surfaced in `AssetDetail.smart_tags`

## Flow
- Each candidate label is wrapped as `"a photo of <label>"` and encoded with CLIP text.
- The image embedding is compared to every label embedding; a softmax over cosine similarities yields probabilities.
- The top-k labels + scores are stored and shown as badges.

## Edge Cases
- ML layer absent → no `tags.json`; `ml_status:"unavailable"`.
- Inference raises → `ml_status:"failed"` with a message; the photo is still ingested/served.
- Video → skipped (documented extension).

## Extension note
The label set is intentionally fixed and small for a reliable demo. Swap in a richer vocabulary, or a different open-vocabulary head, without touching the storage layout — tags always land at `ml/<id>/tags.json`.

## Verification
- Test files: `services/api/tests/test_ingest.py` (ML-present path asserts `tags.json` written and `smart_tags` populated)
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_ingest.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green (CLIP stubbed in tests)

## Related Docs
- [Semantic search](semantic-search.md)
- [ML pipeline](ml-pipeline.md)
