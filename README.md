<!-- last_verified: 2026-08-18 -->
# Immich B2 Backend

A self-hosted **photo-library backend that stores everything on [Backblaze B2](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend)** — a reference for the object-storage pattern that [Immich](https://github.com/immich-app/immich), the popular self-hosted Google-Photos alternative, uses when B2 is its external storage backend.

You add a photo; the app writes the **original** to B2 and then fans it out into **thumbnails**, an **on-device CLIP embedding**, **zero-shot smart tags**, and an **EXIF/metadata sidecar** — every derivative also landing in B2 under Immich-style structured prefixes. B2 becomes the single source of truth for the whole media library: originals, ML artifacts, previews, and metadata, all over the **S3-compatible API**. Semantic search ("beach at sunset") runs against the CLIP embeddings stored in B2.

**For:** privacy-conscious individuals and self-hosters who want full ownership plus unlimited archival capacity on B2, and AI engineers who want a reference for a media pipeline whose storage layer is B2.

**What you get out of the box:**
- Photo ingest → B2 with a real fan-out pipeline (original + thumbnails + EXIF sidecar, always; CLIP embedding + smart tags when the optional ML layer is installed)
- **CLIP semantic search** and **smart tags** powered by real **OpenCLIP** (`open-clip-torch`, model `ViT-B-32`/`openai`) — Immich's own default model
- A scoped **Library** gallery (`library/` prefix) with full asset detail: original, thumbnails, tags, EXIF, embedding status, edit / re-run ML / delete
- The reusable full-bucket **file explorer** (`/files`) that browses every prefix
- FastAPI backend with strict layered architecture and structural tests
- Agent-optimized docs — your AI coding agent can read the repo and start contributing immediately

> **Deploy your own in one click** → [Deploy to Vercel](#deploying-to-vercel). One project, one origin, no CORS to wire up.

## Quick Start

You need: Node.js >= 20, pnpm >= 9, Python >= 3.12, and a free **[Backblaze B2 account](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend)**.

### 1. Get the code

```bash
git clone https://github.com/backblaze-b2-samples/immich-object-storage-backend.git
cd immich-object-storage-backend
```

### 2. Run setup

```bash
pnpm run setup
```

This copies `.env.example` to `.env` (only if missing), installs workspace dependencies, creates `services/api/.venv`, and installs the API's committed Python 3.12 resolution from `services/api/requirements.lock`. It is safe to rerun.

> Use the `pnpm run` form: `setup` (like `doctor`) is a built-in pnpm command before pnpm 11, so bare `pnpm setup` would run pnpm's own command instead of this script.

### 3. Add your B2 credentials

Open `.env` and head to the [Backblaze B2 dashboard](https://secure.backblaze.com/b2_buckets.htm?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend):

1. **Create a bucket.** Paste its **Bucket Unique Name** into `B2_BUCKET_NAME`, and its **region** (shown next to the endpoint, e.g. `us-west-004`) into `B2_REGION`. The S3 endpoint is derived as `https://s3.<B2_REGION>.backblazeb2.com` — you never set an endpoint URL.
2. **Create an application key** with `Read and Write` permission. Paste **keyID** into `B2_APPLICATION_KEY_ID` and **applicationKey** into `B2_APPLICATION_KEY` *(shown once — paste it now)*.

Standardized variable names: `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION` (`B2_PUBLIC_URL_BASE` is optional; the app serves everything via presigned URLs).

### 4. (Optional) Enable the on-device ML layer

The core B2 pipeline (ingest → thumbnails → EXIF → serve → browse) always works. To turn on **semantic search** and **smart tags**, install the optional ML layer — real OpenCLIP, packaged separately exactly like Immich's optional `immich-machine-learning` container:

```bash
services/api/.venv/bin/pip install -r services/api/requirements-ml.txt
```

- First run downloads the `ViT-B-32/openai` weights (~340 MB).
- Runs on **CPU by default**; a CUDA GPU or Apple MPS is auto-detected. Force a device with `ML_DEVICE=cpu|cuda|mps`.
- Without it, photos still ingest and serve; ML endpoints report `ml_status: unavailable`.

### 5. Run it

```bash
pnpm dev
```

Frontend at `localhost:3000`, API at `localhost:8000`. Add a photo, watch it appear in **Library**, then open **Search**. Interactive API docs (Swagger UI) at `localhost:8000/docs`.

`pnpm dev` runs the preflight check first (`pnpm run doctor`) — it catches wrong Node/Python versions, a missing venv, missing or placeholder `.env`, and busy ports.

### Supported local environments

Local scripts run on macOS, Linux, and WSL2 — native Windows isn't supported yet. See [docs/verification.md](docs/verification.md#local-environments) for sandbox, port-fallback, and IPv6 behavior.

## Features

- **[Photo library](docs/features/photo-library.md)** — the `Asset` entity: add, browse, edit metadata, re-run ML, delete. B2 is the source of truth (no database).
- **[Semantic search](docs/features/semantic-search.md)** — text query → CLIP text embedding → cosine rank over embeddings loaded from B2.
- **[Smart tags](docs/features/smart-tags.md)** — zero-shot CLIP classification against a fixed label set.
- **[ML pipeline](docs/features/ml-pipeline.md)** — the ingest fan-out, optional-ML packaging, device autodetect, and graceful degradation.
- **[Photo ingest](docs/features/file-upload.md)** — presigned direct-to-B2 upload of the original, then the derivative pipeline.
- **[Metadata / EXIF sidecar](docs/features/metadata-extraction.md)** — Pillow-extracted EXIF plus editable `description`/`favorite`/`tags`.
- **[File browser](docs/features/file-browser.md)** — the retained full-bucket explorer across every prefix.
- **[Dashboard](docs/features/dashboard.md)** — asset count, storage-by-prefix, the **write-amplification** ratio, and ML-status counts.

## B2 storage layout

B2 is the source of truth. Every asset owns objects under Immich-style prefixes; the library is reconstructed by listing `sidecar/`:

```
library/<user>/<YYYY>/<MM>/<asset_id>.<ext>      original photo (user = "demo", single-tenant)
thumbs/<asset_id>/thumbnail.webp|preview.webp|fullsize.webp
ml/<asset_id>/clip.json                          {model, dim, vector:[...]}
ml/<asset_id>/tags.json                          {model, tags:[{label,score}]}
sidecar/<asset_id>.json                          per-asset source of truth (exif, description, favorite, tags, ml_status, keys)
```

### Write amplification

This is the story the sample makes concrete: one uploaded photo becomes **~2–3× its bytes** across originals + thumbnails + ML artifacts + sidecars. The Dashboard surfaces the exact ratio and the storage-by-prefix breakdown, so you can see B2 holding an entire media library — not just the originals.

## When to use

Use this repository when you want a working reference for a **media pipeline whose storage layer is B2**: photo ingest, derivative fan-out, on-device ML, and semantic search, all persisting to B2 over the S3-compatible API. It is a faithful, minimal model of how Immich uses external object storage, with production-minded engineering controls (strict architecture, contract checks, tests, linting) so you start from a dependable scaffold.

## When not to use

Do not choose this expecting a complete hosted photo service. It does not provide managed hosting, user accounts, authentication, tenant isolation (it is single-tenant, `user_id="demo"`), face recognition, video transcoding, or on-call operations. Before adapting it for production you own its product-specific security, operations, capacity, compliance, and support decisions.

## Why Backblaze B2?

[Backblaze B2](https://www.backblaze.com/cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend) is the object storage this sample is built around — a deliberate default, not just a demo backend:

- **S3-compatible API.** B2 speaks the S3 API, so the `boto3` calls and tooling you already use for AWS S3 work unchanged — you just point them at B2's regional endpoint. This sample uses the S3-compatible API throughout (isolated in `services/api/app/repo/`); nothing is locked to a proprietary client.
- **Built for data-heavy media libraries.** A photo library with originals plus derivatives accumulates fast; B2 storage runs at a fraction of hyperscaler pricing with generous free egress — exactly the write-amplification workload this sample demonstrates.
- **Free to start.** A [free B2 account](https://www.backblaze.com/sign-up/ai-cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend) is enough to run everything here.

## Authenticity to Immich's engine

The headline capability — CLIP semantic search + smart tags — is powered by **OpenCLIP (`open-clip-torch`), model `ViT-B-32`/`openai`**, which is exactly the library and default model Immich's machine-learning service ships. No substitute engine. It is packaged as an **optional, separately-installed layer** (`requirements-ml.txt`), a faithful mirror of Immich's architecture where ML is a **separate, optional `immich-machine-learning` container**: run Immich without it and you simply lose smart search/tags. Same here — the core B2 pipeline always works, and the CLIP layer is the real engine when its deps are installed.

## Tech Stack

- TypeScript, Next.js 16, React 19, Tailwind v4, shadcn/ui
- TanStack Query — caching, dedup, retry for every fetch
- Python 3.12+, FastAPI, boto3, Pydantic v2, Pillow
- **Optional ML:** OpenCLIP (`open-clip-torch`, `ViT-B-32`/`openai`), torch — installed from `requirements-ml.txt`, kept out of the locked core
- Backblaze B2 (S3-compatible object storage)
- pnpm workspaces (monorepo)

## Commands

| Command | What it does |
|---------|-------------|
| `pnpm run setup` | One-time cold start: copy `.env.example` → `.env`, install deps, create the backend venv, install locked API deps |
| `pnpm dev` | Start frontend + backend (runs the `pnpm run doctor` preflight first) |
| `pnpm verify` | Credential-free pre-PR suite — `check:agent-docs`, `verify:api`, then `verify:web` (the ML layer is NOT required) |
| `pnpm contract:export` / `pnpm contract:check` | Export / verify the FastAPI OpenAPI contract in `docs/api/openapi.json` |

`pnpm verify` breaks down into `pnpm check:agent-docs` (agent-doc drift),
`pnpm verify:api` (backend lint, tests, structure), and `pnpm verify:web`
(frontend lint, unit tests, typecheck + build). Use `pnpm verify:full` when
browser/E2E and live-service prerequisites are available. For the full command
reference and worktree/port-fallback notes, see
[docs/dev-workflows.md](docs/dev-workflows.md#commands) and
[docs/verification.md](docs/verification.md).

## Deploying to Vercel

Deploys as **one Vercel project** — the Next.js web app and FastAPI API build from the same repo and share one origin (web at `/`, API under `/api`), so there's **no CORS and no second URL to wire up**. Note that Vercel's serverless runtime cannot run the optional torch/CLIP layer, so a Vercel deploy serves the core B2 pipeline; run ML locally or on a GPU host.

[![Deploy to Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fbackblaze-b2-samples%2Fimmich-object-storage-backend&project-name=immich-object-storage-backend&repository-name=immich-object-storage-backend&demo-title=Immich%20B2%20Backend&demo-description=Self-hosted%20photo%20library%20backend%20that%20stores%20originals%2C%20thumbnails%2C%20CLIP%20embeddings%2C%20smart%20tags%20and%20EXIF%20sidecars%20on%20Backblaze%20B2.&env=B2_APPLICATION_KEY_ID,B2_APPLICATION_KEY,B2_BUCKET_NAME,B2_REGION&envDescription=B2%20credentials%2C%20bucket%20and%20region&envLink=https%3A%2F%2Fgithub.com%2Fbackblaze-b2-samples%2Fimmich-object-storage-backend%2Fblob%2Fmain%2Finfra%2Fvercel%2FREADME.md)

Set your B2 credentials, bucket, and region, and you're live. Uploads go **directly from the browser to B2** (presigned PUT), so Vercel's 4.5 MB payload limit doesn't apply. Two things to know before a real deploy:

- Your bucket's CORS must allow the deploy origin (run `services/api/scripts/setup_b2_cors.py --origin <your origin> --apply`).
- The deployed API is unauthenticated and bucket-wide — use a dedicated B2 bucket/prefix and key for any preview.

Full setup is in the [Vercel delivery contract](infra/vercel/README.md).

## Documentation Map

| Doc | Purpose |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Agent table of contents — start here |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System layout, layering, data flows |
| [docs/features/](docs/features/) | Feature docs (photo library, semantic search, smart tags, ML pipeline, ingest, metadata, browser, dashboard) |
| [docs/app-workflows.md](docs/app-workflows.md) | User journeys |
| [docs/dev-workflows.md](docs/dev-workflows.md) | Engineering workflows, command index, releases |
| [docs/verification.md](docs/verification.md) | What each gate checks, and failure recovery |
| [docs/SECURITY.md](docs/SECURITY.md) | Security principles |
| [docs/api/openapi.json](docs/api/openapi.json) | Checked contract for the sample's local FastAPI API |
| [infra/vercel/README.md](infra/vercel/README.md) | Vercel deployment contract |

## FAQ

**What is the Immich B2 Backend?**
A self-hosted photo-library backend (Next.js 16 + FastAPI) that stores originals, thumbnails, CLIP embeddings, smart tags, and EXIF sidecars on [Backblaze B2](https://www.backblaze.com/cloud-storage?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend). It models the object-storage pattern Immich uses when B2 is its external backend.

**Does it use Immich's real ML engine?**
Yes. Semantic search and smart tags run on real OpenCLIP (`open-clip-torch`) with the `ViT-B-32/openai` model — Immich's own default. It is an optional, separately-installed layer (`requirements-ml.txt`), mirroring Immich's separate ML container.

**Do I have to install the ML layer?**
No. The core B2 pipeline (ingest, thumbnails, EXIF, serve, browse) always works. Without the ML layer, ML endpoints report `unavailable`; install `requirements-ml.txt` to enable search and tags.

**Where do the photos and derivatives live?**
All on B2, under structured prefixes (`library/`, `thumbs/`, `ml/`, `sidecar/`). There is no database — the library is reconstructed by listing the `sidecar/` prefix.

**What is "write amplification"?**
One uploaded photo becomes ~2–3× its bytes once you add thumbnails, ML artifacts, and sidecars. The Dashboard shows the exact ratio and a storage-by-prefix breakdown.

**Does it do face recognition or video ML?**
No. Face recognition (Immich uses InsightFace `buffalo_l`) and video derivatives are documented extension points, deliberately scoped out to keep a single reliable on-device engine. Video originals are stored first-class.

**Is it multi-tenant / does it have auth?**
No. It is single-tenant (`user_id="demo"`) and unauthenticated, like the starter. Add auth and per-user scoping before any shared deployment — see [docs/SECURITY.md](docs/SECURITY.md).

**How do I rebrand it?**
Edit `apps/web/src/lib/app-config.ts` (`APP_NAME`, `APP_DESCRIPTION`); the title, sidebar, and API title follow.

**Does it work on Windows?**
Local scripts are supported on macOS, Linux, and WSL2. Native Windows is not supported yet — use WSL2.

**Where do I get help or report bugs?**
Report defects through GitHub Issues on this repository. For B2 account, billing, service, or API help, use [Backblaze Support](https://www.backblaze.com/help?utm_source=github&utm_medium=referral&utm_campaign=ai_artifacts&utm_content=b2ai-immich-object-storage-backend).

## Maintenance and support

Backblaze maintains this open-source sample to help developers get started with B2. Production use is possible with caution and requires your own validation. This sample is not covered by the Backblaze service level agreement, and no SLA is provided for the repository software; any B2 service or support commitments are governed separately by the applicable Backblaze terms and support plan.

## License

MIT License - see [LICENSE](LICENSE) for details.
