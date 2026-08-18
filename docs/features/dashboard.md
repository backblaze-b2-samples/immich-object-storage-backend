<!-- last_verified: 2026-08-18 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance overview of the photo library on B2: asset count, total bytes, the write-amplification ratio, storage-by-prefix, and ML-status counts.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /assets/stats`

## Core Functions
- `apps/web/src/components/dashboard/library-overview.tsx` — stat cards + storage-by-prefix bars + ML-status list
- `apps/web/src/lib/queries.ts` — `useLibraryStats()`
- `services/api/app/runtime/assets.py` — `GET /assets/stats` handler
- `services/api/app/service/assets.py` — `get_library_stats()`
- `services/api/app/repo/asset_store.py` — `list_prefix()` per prefix

## Canonical Files
- Dashboard layout: `apps/web/src/components/dashboard/library-overview.tsx`
- Stats logic: `services/api/app/service/assets.py`

## Inputs
- None (loads automatically)

## Outputs
- `GET /assets/stats` → `LibraryStats`: `total_assets`, `original_bytes`, `derivative_bytes`, `total_bytes` (+ human), `write_amplification`, `storage_by_prefix`, `ml_status_counts`, `favorites`

## Write amplification
`write_amplification = total_bytes / original_bytes`. It quantifies the headline story: one photo becomes ~2–3× its bytes once thumbnails, ML artifacts, and sidecars are added. `storage_by_prefix` breaks the total across `library/`, `thumbs/`, `ml/`, and `sidecar/`.

## Flow
- Page loads → `GET /assets/stats` sums object sizes per prefix and counts assets from `sidecar/`.
- Stat cards show photos, total on B2, amplification ratio, favorites.
- A storage-by-prefix bar chart and an ML-status breakdown render below.

## Edge Cases
- API unavailable → inline error state with retry.
- Empty library → zeros and a `0×` amplification, no crash.
- Large library → sizes summed per prefix via paginated `list_objects_v2`.

## UX States
- Loading: an escalating "Loading library stats…" notice + skeletons.
- Empty: zero cards; "No assets yet" in the ML panel.
- Loaded: populated cards, bars, and counts.

## Verification
- Test files: `services/api/tests/test_assets.py` (`test_library_stats_reports_amplification`)
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_assets.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [Photo library](photo-library.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [App Workflows](../app-workflows.md)
