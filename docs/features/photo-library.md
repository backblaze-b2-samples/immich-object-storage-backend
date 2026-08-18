<!-- last_verified: 2026-08-18 -->
# Feature: Photo Library (Asset)

## Purpose
Manage photos as first-class `Asset` entities backed entirely by B2 — add, browse, edit metadata, re-run ML, and delete — with no database (the library is reconstructed from `sidecar/` objects).

## Used By
- UI: `/library` (scoped gallery + asset-detail dialog), plus the `/` dashboard and `/search`
- API: `GET /assets`, `GET /assets/detail`, `POST /assets/update`, `POST /assets/rerun`, `DELETE /assets`, `GET /assets/original-url`, `GET /assets/thumbnail-url`, `GET /assets/stats`

## Core Functions
- `services/api/app/service/assets.py` — list/get/update/delete/rerun + stats + presigned URLs
- `services/api/app/repo/asset_store.py` — structured-prefix reads/writes (the only boto3 for assets)
- `services/api/app/runtime/assets.py` — route handlers
- `services/api/app/types/assets.py` — `AssetSummary`, `AssetDetail`, `AssetUpdate`, `LibraryStats`
- `apps/web/src/components/library/*` — gallery, card, detail dialog
- `apps/web/src/lib/queries.ts` — `useAssets`, `useAsset`, `useUpdateAsset`, `useDeleteAsset`, `useRerunAssetMl`

## Canonical Files
- Asset service logic: `services/api/app/service/assets.py`
- Edit-form UX exemplar: `apps/web/src/components/library/asset-detail-dialog.tsx`

## Inputs
- create: a photo file (via `/upload`, presigned PUT)
- edit: `AssetUpdate` (`description`, `favorite`, `tags` — free text)
- read/run/delete: `asset_id` (string)

## Outputs
- `AssetSummary[]` / `AssetDetail` (JSON)
- side effects on B2: sidecar rewrite (edit), cascade delete of all derivative keys (delete), overwrite of `ml/` + `thumbs/` (re-run)

## Primary-entity lifecycle (all five verbs)
| Verb | UI surface | Effect on B2 |
|------|-----------|--------------|
| create | `/upload` | presigned PUT original → ingest fans out derivatives |
| read | `/library` gallery + detail dialog | presigned GET original/thumbnails; read sidecar/tags |
| edit | detail dialog → description/favorite/tags | rewrite `sidecar/<id>.json` |
| delete | detail dialog (confirm) | `delete_object` original + cascade all derivatives |
| run | detail dialog → "Re-run ML processing" | regenerate embedding + tags + thumbnails |

`omitted_ui_verbs` is empty.

## Flow
- Gallery loads → `GET /assets` lists `sidecar/`, hydrates a card grid; each card lazily fetches its thumbnail presigned URL.
- Open a card → `GET /assets/detail` (sidecar + ml docs) + `GET /assets/original-url` (inline presigned original).
- Edit form pre-fills from the real sidecar; Save → `POST /assets/update` rewrites the sidecar.
- Delete → confirm → `DELETE /assets` cascades every key the asset owns.
- Re-run ML → `POST /assets/rerun` re-runs the ingest fan-out, preserving user edits.

## Edge Cases
- Missing sidecar → 404 `AssetNotFoundError`.
- Invalid `asset_id` (path-traversal chars) → 400 `AssetIdError`.
- Thumbnail not generated (video, or Pillow decode failure) → card shows an icon placeholder.
- Re-run when the ML layer is absent → thumbnails still regenerate; `ml_status` stays `unavailable`.

## UX States
- Empty: "Your library is empty" with an Add-photos CTA.
- Loading: skeleton grid.
- Error: inline `ErrorState` with retry.

## Verification
- Test files: `services/api/tests/test_assets.py`
- Required cases: list/get, update persists, cascade delete, re-run preserves edits, stats/amplification, invalid id
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_assets.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [ML pipeline](ml-pipeline.md)
- [App Workflows](../app-workflows.md)
