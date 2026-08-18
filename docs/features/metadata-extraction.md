<!-- last_verified: 2026-08-18 -->
# Feature: EXIF Sidecar + Editable Metadata

## Purpose
Extract each photo's EXIF and dimensions at ingest (Pillow), and let the user edit `description`, `favorite`, and `tags` — all persisted to the asset's `sidecar/<id>.json` on B2, the per-asset source of truth.

## Used By
- UI: asset-detail dialog (EXIF facts + edit form)
- API: written by ingest / re-run; read via `GET /assets/detail`; edited via `POST /assets/update`

## Core Functions
- `services/api/app/service/ingest.py` — `_extract_image_meta()` (width/height + flattened EXIF)
- `services/api/app/service/assets.py` — `update_asset()` (rewrites the sidecar)
- `services/api/app/service/metadata.py` — richer on-demand extraction reused by the `/files` browser
- `apps/web/src/components/library/asset-detail-dialog.tsx` — the edit-metadata form

## Canonical Files
- Sidecar/EXIF extraction: `services/api/app/service/ingest.py`
- Edit-form UX exemplar: `apps/web/src/components/library/asset-detail-dialog.tsx`

## Inputs
- ingest: image bytes → EXIF + dimensions
- edit: `AssetUpdate` (`description` textarea, `favorite` switch, `tags` free-text/comma-separated)

## Outputs
- `sidecar/<id>.json` carrying `exif`, `image_width/height`, `description`, `favorite`, `tags`, `ml_status`, and pointers to every derivative key
- surfaced in `AssetDetail`

## Form UX
Finite-value fields would use a selector, but the edit form here is deliberately free text where the vocabulary is unbounded: `favorite` = Switch, `description` = Textarea, `tags` = comma-separated Input (open vocabulary → free text is correct, not a selector). The create form (`/upload`) hints safe defaults via placeholder/description, never an autofill button.

## Flow
- Ingest extracts EXIF + dimensions and folds them into the sidecar.
- Opening the detail dialog pre-fills the edit form from the real sidecar.
- Save → `POST /assets/update` rewrites only the provided fields; blanks in `tags` are dropped.

## Edge Cases
- No EXIF / undecodable image → sidecar still written with `exif: null` (dimensions may be null).
- Decompression-bomb image (via the `/files` on-demand path) → extraction skipped with a warning; checksums stay exact.

## UX States
- Detail dialog: facts table + up to 6 EXIF rows; edit form with save-pending state and a success toast.

## Verification
- Test files: `services/api/tests/test_assets.py` (`test_update_asset_rewrites_sidecar`), `services/api/tests/test_ingest.py` (EXIF/dimensions), `services/api/tests/test_metadata_warning.py`
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_assets.py tests/test_ingest.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [Photo library](photo-library.md)
- [ML pipeline](ml-pipeline.md)
