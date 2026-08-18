# Scaffold plan — `immich-object-storage-backend`

Source of truth (Phase 0 clone, the ONLY valid starter source):
`.claude/scratch/vcsk-00ecf78a-53e2-43b8-8f68-174f901609a3/`
Build target: `./immich-object-storage-backend` (under `sampleapps/.local/`).

---

## 1. Purpose

A self-hosted **photo-library backend that stores everything on Backblaze B2**,
demonstrating the object-storage pattern [Immich](https://github.com/immich-app/immich)
(the popular self-hosted Google-Photos alternative) uses when B2 is its external
storage backend. You add photos; the app writes the **original** to B2 and then fans
out the same asset into **thumbnails**, an **on-device CLIP embedding**, **smart
tags**, and an **EXIF/metadata sidecar** — every derivative also landing in B2 under
Immich-style structured prefixes. This makes the **write-amplification** story
concrete (one 8 MB photo becomes ~2–3× its bytes across originals + thumbs + ML +
sidecars) and shows B2 acting as the single source of truth for an entire media
library: originals, ML artifacts, previews, and metadata, all over the
**S3-compatible API**. Semantic search ("beach at sunset") runs against the
CLIP embeddings stored in B2. For: privacy-conscious individuals/families and
self-hosters who want full ownership + unlimited archival capacity on B2, and AI
engineers who want a reference for a media pipeline whose storage layer is B2.

**Authenticity to the vendor's engine (local convention):** the headline capability
— CLIP semantic search + zero-shot smart tags — is powered by **OpenCLIP
(`open-clip-torch`), model `ViT-B-32` / `openai`**, which is exactly the library and
default model Immich's machine-learning service ships. No substitute engine. It is
packaged as an **optional, separately-installed layer** (`requirements-ml.txt`),
which is not a downgrade but a faithful mirror of Immich's real architecture, where
ML is a **separate, optional `immich-machine-learning` container** — run Immich
without it and you simply lose smart search/tags. Same here: the core B2 pipeline
(ingest → thumbnails → EXIF → serve → browse) is fully wired and always works; the
CLIP layer is the real engine when its deps are installed, and degrades gracefully
("ML pending / not installed") when they are not. This keeps `pnpm verify` green
without a 300 MB torch install and contains native-ML crashes (local convention).

---

## 2. Architecture delta from `vibe-coding-starter-kit`

The starter kit is the ceiling — strip what a photo-library backend doesn't need,
keep the reusable B2 scaffolding, add the photo/ML surface.

| KEEP (as-is) | TRIM (remove) | ADD (new) |
|---|---|---|
| **UI kit / design system** — `apps/web/src/components/ui/**`, `globals.css` tokens, `/design` page (starter contract, never edit `ui/`) | Starter README **branding screenshots refs** (`docs/images/b2-starterkit-*.png` — the PNGs were already stripped by fetch, so the `![…]()` refs are now **broken links** that fail `check:agent-docs`; remove them) | **`/library`** route — sample-specific **asset explorer scoped to the `library/` prefix**: a photo thumbnail-grid gallery of the app's own assets (the mandated scoped explorer, analogous to a TTS "Library of audio files") |
| **Full-bucket file explorer** — `/files`, `apps/web/src/app/files/**`, `components/files/**`, the **Files** sidebar entry (**NON-NEGOTIABLE KEEP** — browses every prefix: `library/ thumbs/ ml/ sidecar/`) | Dashboard's generic stat cards / recent-uploads semantics (rewrite, don't delete the route) | **`/search`** route — CLIP **semantic search**: text query → CLIP text embedding → cosine rank over embeddings loaded from B2 |
| **Upload** — `/upload`, `app/upload/**`, `components/upload/**`, presigned **direct-to-B2 PUT** path (handles 3–50 MB photos, bypasses proxy limits), the Upload sidebar entry | `docs/features/*` that no longer map (see §5) | **Asset detail** view (in `/library`) — original (presigned inline URL) + thumbnails + tags + EXIF + embedding status; **edit metadata**, **re-run ML**, **delete** actions |
| Layout: sidebar, header, command palette, health banner, theme provider, error/loading/not-found | — | **Ingest pipeline** (`services/api/app/service/ingest.py` + repo adapters): after upload-verify, generate thumbnails (Pillow) + EXIF sidecar + (optional) CLIP embedding + smart tags, all written to B2 |
| Settings (`/settings`) showcase + the Settings sidebar entry (nav stays) | — | **`repo/asset_store.py`** (structured-prefix reads/writes), **`repo/ml_clip.py`** (lazy CLIP adapter, device autodetect), **`repo/embedding_index.py`** (load embeddings from B2, cosine search) |
| Backend layering `types→config→repo→service→runtime`; TanStack Query in `lib/queries.ts`; OpenAPI contract; all verify gates & `check:agent-docs` | — | New `docs/features/*` (§5); `requirements-ml.txt` (optional torch/open-clip/numpy) |
| Presigned-URL serving (works for private buckets — default) | — | Dashboard rewrite: assets, library size, **write-amplification ratio**, storage-by-prefix breakdown, ingest activity, ML-status counts |

**Bucket-explorer tension note:** none. `/files` (full-bucket) is kept verbatim as
the mandated bucket explorer; `/library` is the *additional* sample-scoped explorer.
Both ship.

---

## 3. B2 surface (S3-compatible API only — **no b2-native**)

All access via boto3 S3 client in `repo/` (AGENTS.md: no boto3 outside `repo/`).
Repo-root default is S3-only; **zero b2-native calls** planned or justified.

| S3 operation | Used for |
|---|---|
| `generate_presigned_url` (PUT) | Browser uploads **original** photo directly to B2 (kept from starter) |
| `generate_presigned_url` (GET, inline/attachment) | Serve originals + thumbnails in gallery/detail; downloads |
| `put_object` | Write derivatives: thumbnails, `clip.json`, `tags.json`, EXIF sidecar |
| `get_object` / Range GET | Download original for ingest processing; load embeddings for search; magic-byte sniff (kept) |
| `list_objects_v2` (paginated, cached) | Full-bucket explorer, `/library` gallery (prefix `library/`), dashboard stats, load all embeddings |
| `head_object` | Metadata, health check (kept) |
| `delete_object` | Delete asset + **cascade** all derivatives (`library/…`, `thumbs/<id>/*`, `ml/<id>/*`, `sidecar/<id>.json`) |

**Custom user agent:** `user_agent_extra="b2ai-immich-object-storage-backend"` on the
single cached S3 client (b2-doctor Check 2).

**Standardized env vars — MANDATORY round-1 transform (b2-doctor Checks 3 & 4 will
❌ the starter's names/hardcoded region):** the starter ships `B2_ENDPOINT`,
`B2_KEY_ID`, `B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_PUBLIC_URL` and a hardcoded
`us-west-004` default in `settings.py`. Convert to the standard set:

- `.env.example` (exactly, no aliases): `B2_APPLICATION_KEY_ID`, `B2_APPLICATION_KEY`,
  `B2_BUCKET_NAME`, `B2_REGION` (all four uncommented) + `B2_PUBLIC_URL_BASE`
  (may be a commented line — functionally optional; app serves via presigned URLs).
- `settings.py`: fields `b2_application_key_id`, `b2_application_key`, `b2_bucket_name`,
  `b2_region` (**default `""` — no hardcoded region**), `b2_public_url_base` (default `""`).
- `b2_client.py`: derive `endpoint_url=f"https://s3.{settings.b2_region}.backblazeb2.com"`;
  `aws_access_key_id=settings.b2_application_key_id`,
  `aws_secret_access_key=settings.b2_application_key`; `_public_url` uses `b2_public_url_base`.
- `main.py`: update `REQUIRED_B2_SETTINGS` + `PLACEHOLDER_VALUES` to the new names.
- Sweep every referencer: `tests/conftest.py` + affected tests, `scripts/setup_b2_cors.py`,
  `scripts/doctor.mjs`, `setup.mjs`, README, `infra/vercel/README.md`, and the
  **Vercel deploy button** query string in `README.md:240` (`env=…` currently lists
  `B2_KEY_ID,…,B2_ENDPOINT`; change to the standard names and drop the dead
  `demo-image` PNG). Run `pnpm contract:export` if any route/shape changed.
- No hardcoded region anywhere except code comments / docs examples (b2-doctor Check 4).

**B2 storage layout (Immich-style prefixes):**
```
library/<user_id>/<YYYY>/<MM>/<asset_id>.<ext>   # original (user_id = "demo", single-tenant)
thumbs/<asset_id>/thumbnail.webp|preview.webp|fullsize.webp
ml/<asset_id>/clip.json      # {model, dim, vector:[...]}
ml/<asset_id>/tags.json      # {tags:[{label,score}], model}
sidecar/<asset_id>.json      # source of truth per asset: exif, description, favorite, tags, ml_status, keys
```
No database (matches starter) — **B2 is the source of truth**; the library is
reconstructed by listing `sidecar/` (each sidecar carries `ml_status ∈
pending|done|failed|unavailable` and pointers to its derivative keys).

---

## 4. Key features

Per-feature `deployment:` is explicit (builder + reviewer gate on it). No external
API provider is used anywhere (description: "no second API key, B2 credentials
only") → **no provider env keys**. **Genblaze: NOT used** — the description never
mentions Genblaze / `genblaze-*` / `genblaze-s3`; storage stays plain boto3 in `repo/`.

1. **Continuous media ingest → B2** · `deployment: local` (no external API) — upload
   photos; original stored to `library/<user>/<YYYY>/<MM>/` via presigned PUT, then
   the ingest pipeline runs. Always works (pure B2 + Pillow).
2. **On-device CLIP semantic search** · `deployment: local` — engine **OpenCLIP
   `open-clip-torch`, `ViT-B-32`/`openai`** (Immich's default model). Image embeddings
   computed at ingest → `ml/<id>/clip.json`; text query embedded + cosine-ranked over
   embeddings loaded from B2. **CPU default, autodetect CUDA→MPS→CPU** (`ML_DEVICE`
   override); MPS caveat: torch MPS is usable but if it errors, fall back CUDA→CPU.
   Cost: **$0** (on-device). Optional install (`requirements-ml.txt`); degrades to
   "ML not installed / pending" when absent.
3. **On-device smart tags** · `deployment: local` — **same CLIP model**, zero-shot
   classification against a fixed label set → `ml/<id>/tags.json`. Cost $0. Same
   optional-ML layer + graceful degradation.
4. **Thumbnail generation (write amplification)** · `deployment: local` — Pillow
   makes `thumbnail`/`preview`/`fullsize` WEBP per asset → `thumbs/<id>/`; dashboard
   surfaces the derived-vs-original amplification ratio. No ML; always works.
5. **EXIF sidecar + editable metadata** · `deployment: local` — Pillow extracts EXIF
   → `sidecar/<id>.json`; user-editable `description`/`favorite`/`tags` written back
   to B2. No ML.
6. **Photo gallery + full-bucket explorer** · `deployment: local` — `/library`
   scoped asset explorer (thumbnail grid + detail) plus the retained `/files`
   full-bucket browser.

### Primary-entity lifecycle (mandatory UI completeness)

**Primary entity: `Asset` (a photo).** All five verbs are user-accessible → the UI
builds every one; **`omitted_ui_verbs` is empty** (no justification needed).

| Verb | UI surface | Effect on B2 |
|---|---|---|
| **create** | `/upload` (adapted copy: "Add photos to your library") | presigned PUT original → ingest fans out derivatives |
| **read** | `/library` gallery + asset-detail panel | presigned GET original/thumbnails; read sidecar/tags |
| **edit** | asset-detail → edit `description`/`favorite`/`tags` | rewrite `sidecar/<id>.json` |
| **delete** | asset-detail + gallery hover action (confirm dialog) | `delete_object` original + cascade all derivatives |
| **run** | asset-detail → **"Re-run ML processing"** | regenerate embedding + tags (+ thumbnails) → overwrite `ml/…`, `thumbs/…` |

Every new write flows `runtime → service → repo`; every fetch through a TanStack
Query hook in `lib/queries.ts` (no bare `useEffect+fetch`); every route change
re-exports `docs/api/openapi.json` and updates `API_CLIENT_ROUTES` +
`api-contract.test.ts` (backend-only routes go in `SERVER_ONLY_OPERATIONS`).

### Form UX conventions

Exemplar to match: `apps/web/src/components/settings/settings-form.tsx`
(react-hook-form + zod + shadcn `Form`; finite-value fields use `Select`/`RadioGroup`;
create forms hint safe defaults via placeholder / `FormDescription`, never an autofill
button).

- **Upload (create) form:** file dropzone (kept). Any finite-choice control (e.g. a
  future album/visibility selector) uses `Select`/`RadioGroup`. Surface safe-default
  guidance as placeholder/`FormDescription` (e.g. "JPEG/PNG/HEIC up to 100 MB — try a
  landscape photo to see semantic search light up"). Guidance only, no autofill.
- **Edit-metadata form (edit):** opens pre-filled from the real sidecar. `favorite`
  = `Switch`; `tags` = token input / free text (open vocabulary — genuinely unbounded,
  so free text is correct, not a selector); `description` = `Textarea`. Selector rule
  applies only where the value set is finite.

---

## 5. Doc transforms

**Rewrite:**
- `README.md` — new purpose, quick start (adds: optional ML install
  `pip install -r services/api/requirements-ml.txt`, first-run model download
  ~340 MB, CPU default / GPU autodetect), feature list (§4), **B2 storage-layout
  diagram**, write-amplification explanation, **When to use / When not to use**, and a
  **FAQ** (AEO value). Remove broken `docs/images/b2-starterkit-*.png` refs; fix the
  Vercel button (standard env names, drop dead `demo-image`). Order for humans: CTA/quick
  start + (later-added) screenshots high; governance/SLA/deep-dive low.
- `docs/features/dashboard.md` — photo-library metrics + amplification ratio.
- `docs/features/file-upload.md` → photo ingest + the fan-out pipeline.
- `docs/features/metadata-extraction.md` → EXIF sidecar + editable metadata.
- `ARCHITECTURE.md`, `docs/app-workflows.md`, `docs/dev-workflows.md`,
  `docs/SECURITY.md` (single-tenant `user_id="demo"` stance stays; note cascade-delete
  + optional-ML boundary), `docs/verification.md` (ML is optional/not in core lock),
  `PRODUCT.md`, `AGENTS.md` repo map + shims — reflect the new app + rename.

**New feature stubs (`docs/features/_template.md` shape):**
- `docs/features/photo-library.md` — the `Asset` entity + gallery + full lifecycle.
- `docs/features/semantic-search.md` — CLIP query path; embeddings in B2; extension
  note (production → vector DB; Immich uses pgvecto.rs).
- `docs/features/smart-tags.md` — zero-shot CLIP tagging.
- `docs/features/ml-pipeline.md` — ingest fan-out; optional-ML packaging (mirrors
  Immich's separate ML container); device autodetect; graceful degradation; **face
  recognition documented as a scoped-out extension point** (Immich uses InsightFace
  `buffalo_l`; omitted here to keep a single reliable on-device engine and contain
  onnxruntime macOS crashes — the `ml/<id>/` prefix reserves room for `faces.json`).

**Keep (light touch):** `docs/features/file-browser.md`, `docs/features/settings.md`,
`docs/RELIABILITY.md`, `docs/frontend-conventions.md`. Delete stale completed
exec-plans only if they name the old identity misleadingly (prefer keep).

---

## 6. Rename table

Apply repo-wide (grep the two dozen files found in scan). `<sample-name>` =
`immich-object-storage-backend` = package.json `name`.

| From | To |
|---|---|
| `vibe-coding-starter-kit` (root pkg name, workspace refs, URLs) | `immich-object-storage-backend` |
| `@vibe-coding-starter-kit/web` / `@vibe-coding-starter-kit/shared` | `@immich-object-storage-backend/web` / `@immich-object-storage-backend/shared` |
| `Vibe Coding Starter Kit` (APP_NAME in `app-config.ts`; API title derives from it) | `Immich B2 Backend` |
| `File management dashboard template powered by Backblaze B2` (APP_DESCRIPTION) | `Self-hosted photo library backed by Backblaze B2 object storage` |
| `b2ai-oss-start` (UA `user_agent_extra` **and** all `utm_content=` in `.md` + sidebar link + Vercel button) | `b2ai-immich-object-storage-backend` (branding.mjs enforces UA == utm_content) |
| `vibe_coding_starter_kit` (snake, if any) | `immich_object_storage_backend` |
| Image tags / workflow slugs / `railway.json` / `vercel.json` names referencing the old slug | `immich-object-storage-backend` |
| B2 env names `B2_KEY_ID`/`B2_ENDPOINT`/`B2_PUBLIC_URL` | `B2_APPLICATION_KEY_ID` / (`B2_REGION`→derived endpoint) / `B2_PUBLIC_URL_BASE` (see §3) |

`app-config.ts` stays the single source for the display name (components import
`APP_NAME`; do not hardcode it elsewhere — branding.mjs check).

---

## Notes / risks (for reviewer — not defects)

- **Optional-ML packaging is deliberate**, not a stubbed/substitute engine: real
  OpenCLIP `ViT-B-32/openai` (Immich's own model) runs when `requirements-ml.txt` is
  installed; it is separated exactly like Immich's optional ML container so core
  `pnpm verify` stays green without torch and to contain native-ML crashes. **ML deps
  must be lazy-imported inside adapter functions** so `pytest` and module import
  succeed without torch; ML endpoints/pipeline return a clear "unavailable" state and
  the asset is still ingested/served/browsable. Later pipeline steps (sample-3-verify,
  sample-4-screenshot) install the ML layer to exercise/capture the real CLIP path.
- **Dependency lock:** heavy ML deps stay OUT of the locked core `requirements.txt` /
  `requirements.lock` (they live in `requirements-ml.txt`), so `test_dependency_lock`
  stays satisfied without regenerating the lock for a 300 MB torch tree. Pillow is
  already core (thumbnails/EXIF need no new core dep). If cosine search needs numpy,
  numpy goes in `requirements-ml.txt` (or do cosine in pure Python).
- **Video** (MP4/MOV): stored to B2 as first-class originals; thumbnail + ML
  derivatives for video are a documented extension (needs ffmpeg) — the full
  ingest→derivative→search demo runs on **images** to keep the headline reliable.
- **Semantic search** is brute-force cosine over B2-loaded embeddings (fine for a demo
  library); production → vector DB (documented).
- **Backend invariants:** boto3 only in `repo/`; new `app/` Python files < 300 lines;
  structured JSON logging (no `print`); Pydantic models at boundaries; update OpenAPI
  contract + client routes on every route change.
- **No binary assets / screenshots** created here (later pipeline step); **no push**;
  no touching sibling samples in `../`.
