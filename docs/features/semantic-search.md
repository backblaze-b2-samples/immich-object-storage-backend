<!-- last_verified: 2026-08-18 -->
# Feature: Semantic Search

## Purpose
Find photos by meaning ("beach at sunset"), not filename, by embedding the text query with the same CLIP model that indexed each photo and cosine-ranking it against the embeddings stored in B2.

## Used By
- UI: `/search`
- API: `GET /search?q=<text>&limit=<n>`

## Core Functions
- `services/api/app/service/search.py` — orchestrates availability check, embedding load, query embed, rank, hydrate
- `services/api/app/repo/ml_clip.py` — `embed_text()` (real OpenCLIP)
- `services/api/app/repo/embedding_index.py` — `load_all_embeddings()`, `cosine_similarity()`, `rank()` (pure Python, no numpy)
- `apps/web/src/components/search/search-view.tsx` — query box, example chips, results grid
- `apps/web/src/lib/queries.ts` — `useSearch`

## Canonical Files
- Search service: `services/api/app/service/search.py`

## Inputs
- `q`: string (text query)
- `limit`: int (1–100, default 24)

## Outputs
- `SearchResponse` = `{ query, ml_status: "ok"|"unavailable", message, results: [{asset, score}] }`

## Flow
- `GET /search` → if the ML layer is absent, return `ml_status:"unavailable"` with install guidance (never 500).
- Load every `ml/<id>/clip.json` from B2 into memory.
- Embed the query text with CLIP (`ViT-B-32/openai`).
- Cosine-rank against all embeddings; hydrate the top matches into `AssetSummary` from the sidecars.

## Edge Cases
- ML layer not installed → `unavailable` + guidance.
- No embeddings yet (photos ingested without ML) → `ok` with a "re-run ML" message and empty results.
- Empty query → 400.
- Query embedding raises → reported as `unavailable`, not a 500.

## UX States
- Empty (no query): example chips.
- Loading: skeleton grid.
- Unavailable / no-embeddings: an informational alert.
- Results: a scored thumbnail grid; each card opens the shared asset-detail dialog.

## Extension note
This is brute-force cosine over B2-loaded embeddings — fine for a demo library. Production would push embeddings into a vector database; Immich uses `pgvecto.rs`.

## Verification
- Test files: `services/api/tests/test_search.py`
- Required cases: unavailable without ML, cosine ranking with distinct embeddings, no-embeddings message, pure-Python cosine
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_search.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green (the ML layer is stubbed in tests)

## Related Docs
- [ML pipeline](ml-pipeline.md)
- [Smart tags](smart-tags.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
