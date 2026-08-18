<!-- last_verified: 2026-08-06 -->
# Architecture

This sample is a self-hosted photo-library backend that stores originals and
every derivative (thumbnails, CLIP embeddings, smart tags, EXIF sidecars) on
Backblaze B2 — the object-storage pattern Immich uses with an external backend.

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Dashboard: asset count, storage-by-prefix, write-amplification ratio, ML-status counts
  - Library: scoped `library/` gallery + asset-detail (edit / re-run ML / delete)
  - Semantic search: text → CLIP → cosine over B2 embeddings
  - Upload: presigned direct-to-B2 photo ingest
  - File browser: the retained full-bucket explorer across every prefix
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - Photo ingest fan-out + asset lifecycle + semantic search
  - B2 S3 integration via boto3 (whole-bucket + structured-prefix stores)
  - **Optional on-device ML** — real OpenCLIP (`ViT-B-32`/`openai`), installed
    separately from `requirements-ml.txt`, lazy-imported, degrades gracefully
  - Health check, structured JSON logging, Prometheus-format metrics
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API (files + assets)
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access (boto3 B2 client) — no business logic
  |
service/   Business logic — calls repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` only allowed in `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Authored Python files under `services/api/app/` stay under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  requirements.txt/.lock   Locked core deps (NO torch — stays green in verify)
  requirements-ml.txt      Optional CLIP layer (torch, open-clip-torch, numpy)
  app/
    types/                 Pydantic models (files.py, assets.py, upload.py, stats.py)
    config/                Settings loaded from environment
    repo/                  Data access — boto3 only here
      b2_client.py         Whole-bucket client (list/head/delete/presign)
      asset_store.py       Structured-prefix store (library/thumbs/ml/sidecar)
      ml_clip.py           Lazy OpenCLIP adapter (device autodetect, MPS fallback)
      embedding_index.py   Load embeddings from B2 + pure-Python cosine rank
    service/               Business logic (upload, ingest, assets, search, files, metadata)
    runtime/               FastAPI route handlers (upload, assets, search, files, health, metrics)
  tests/                   pytest tests (structural + integration)
```

## Boundary Invariants

- **No external SDK leakage**: `boto3` is only imported in `app/repo/`. All other layers interact with B2 through the repo interface.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No cross-layer mutable state**: Configuration is read-only after init, and no mutable state is shared *between* layers. Intra-layer caches/counters (the listing cache in `repo/list_cache.py`, the B2 connectivity cache in `repo/b2_client.py`, the download counter in `repo/counter.py`, the rate-limit and metrics state in `runtime/`) are module-local and guarded by a `threading.Lock`. The listing cache also owns the only background thread in the app: a stale entry is served immediately while that thread re-scans (stale-while-revalidate), and `main.lifespan` warms it once at startup so no user pays for the cold full-bucket scan.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys reject empty and path-traversal patterns; optional prefix confinement via `ALLOWED_KEY_PREFIX` (off by default).

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently`
  - Web: `localhost:3000`
  - API: `localhost:8000`
- **Railway** — two services from the same repository: `web` builds from the
  repository root because it consumes `packages/shared`; `api` builds from
  `services/api`. Each service's versioned config sits at its own root —
  `railway.json` and `services/api/railway.json` — the default path Railway
  discovers, so a one-click template deploy inherits the same build, start, and
  health behavior with nothing to configure by hand. The human-approved
  staging/production contract lives in [infra/railway/README.md](infra/railway/README.md).
- **Vercel** — one project using [Vercel Services](https://vercel.com/docs/services):
  the `web` (Next.js) and `api` (FastAPI) services build from the same repo and
  share one origin — the web app at `/`, the API under `/api`. The repo-root
  `vercel.json` declares both services and routes `/api/*` to the API service;
  the Vercel-only `services/api/index.py` strips the `/api` prefix so FastAPI
  keeps its native paths (`/health`, `/files`, …). Uploads go directly from the
  browser to B2 via a presigned PUT (see
  [File Upload](docs/features/file-upload.md)), so they bypass the Function's
  4.5 MB payload ceiling entirely — the bucket must allow the deploy origin in
  its CORS. A two-separate-Projects alternative and the full delivery contract
  live in [infra/vercel/README.md](infra/vercel/README.md).

External provisioning and deployment remain explicit user-approved actions.

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API), the sole data store
  - No application database — the library is reconstructed by listing `sidecar/`
  - Each asset owns objects under Immich-style structured prefixes:

```
library/<user>/<YYYY>/<MM>/<asset_id>.<ext>   original (user = "demo")
thumbs/<asset_id>/thumbnail.webp|preview.webp|fullsize.webp
ml/<asset_id>/clip.json                        {model, dim, vector:[...]}
ml/<asset_id>/tags.json                        {model, tags:[{label,score}]}
sidecar/<asset_id>.json                        per-asset source of truth
```

  - Write amplification is the headline: one photo becomes ~2–3× its bytes across
    originals + thumbnails + ML + sidecars (the dashboard surfaces the ratio).

## External Services

- **Backblaze B2 S3 API** — file storage, retrieval, deletion, presigned URLs

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s — otherwise the browser would block error responses and the UI would only see an opaque "network error". See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling). A per-IP rate-limit middleware sits inner to CORS; see [docs/SECURITY.md](docs/SECURITY.md#rate-limiting).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for download (10-min expiry, forced attachment)

## Data Flows

- **Ingest (create)**: Browser -> `POST /upload/presign` (mint a `library/` key + sign a PUT) -> Browser PUTs bytes **directly to B2** -> `POST /upload/verify` (HEAD + Range-sniff, then `ingest_asset()` fans out thumbnails + EXIF sidecar + optional CLIP embedding/tags to B2)
- **Library (read)**: Browser -> `GET /assets` (list `sidecar/`) / `GET /assets/detail` / `GET /assets/original-url` / `GET /assets/thumbnail-url`
- **Edit**: Browser -> `POST /assets/update` -> rewrite `sidecar/<id>.json`
- **Re-run ML (run)**: Browser -> `POST /assets/rerun` -> re-run the ingest fan-out, preserving user edits
- **Delete**: Browser -> `DELETE /assets` -> cascade delete original + all derivatives
- **Search**: Browser -> `GET /search?q=` -> `ml_clip.embed_text` -> cosine rank over embeddings loaded from B2
- **Full-bucket explorer**: Browser -> `GET /files` / `/files/{key}/…` (retained, browses every prefix)

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (logs duration per request; also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format: request count, latency, upload count)
- `/health` endpoint (B2 connectivity check)

## API Contract

- Checked-in OpenAPI artifact: `docs/api/openapi.json`
- Export/check command: `pnpm contract:export` / `pnpm contract:check`
- FastAPI freshness test: `services/api/tests/test_openapi_contract.py`
- Frontend route drift test: `apps/web/src/lib/api-contract.test.ts`

The frontend client keeps a small `API_CLIENT_ROUTES` registry in
`apps/web/src/lib/api-client.ts`. Tests compare that registry to the checked-in
OpenAPI artifact so route changes fail loudly before the hand-written client can
silently drift from FastAPI. `GET /metrics` is intentionally server-only.

## Canonical Files

- Layered API handler: `services/api/app/runtime/upload.py`, `runtime/assets.py`
- Service orchestration: `services/api/app/service/upload.py`, `service/ingest.py`, `service/assets.py`, `service/search.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`, `repo/asset_store.py`
- On-device ML adapter: `services/api/app/repo/ml_clip.py`, `repo/embedding_index.py`
- Pydantic models: `services/api/app/types/` (`files.py`, `assets.py`, `upload.py`, `stats.py`, `formatting.py`)
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- OpenAPI contract: `docs/api/openapi.json`
- OpenAPI exporter: `services/api/scripts/export_openapi.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Optional ML boundary

The CLIP layer (`repo/ml_clip.py`, `repo/embedding_index.py`) is real OpenCLIP
but **optional**: torch/open_clip are lazy-imported inside functions and live in
`requirements-ml.txt`, kept out of the locked core so `pnpm verify` and
`test_dependency_lock` stay green without a ~300 MB install. When the deps are
absent (or inference fails), ingest still stores the original + thumbnails +
EXIF sidecar and reports `ml_status ∈ {pending, unavailable, failed}`; search
reports `unavailable`. This mirrors Immich's separate, optional ML container.
Face recognition and video derivatives are documented, scoped-out extensions.

## Core Features

- [Photo Library](docs/features/photo-library.md)
- [Semantic Search](docs/features/semantic-search.md)
- [Smart Tags](docs/features/smart-tags.md)
- [ML Pipeline](docs/features/ml-pipeline.md)
- [Photo Ingest](docs/features/file-upload.md)
- [Metadata / EXIF Sidecar](docs/features/metadata-extraction.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
