<!-- last_verified: 2026-08-18 -->
# Feature: Photo Ingest (upload → B2 → fan-out)

## Purpose
Add a photo to the library: the browser uploads the original directly to B2 (presigned PUT), then the API verifies it and runs the ingest fan-out that produces every derivative.

## Used By
- UI: `/upload` ("Add photos to your library")
- API: `POST /upload/presign`, `POST /upload/verify`

## Core Functions
- `apps/web/src/components/upload/*` — dropzone + queue + progress (kept from the starter)
- `apps/web/src/lib/api-client.ts` — `uploadFile()` (presign → PUT → verify, carrying the real filename)
- `services/api/app/service/upload.py` — declared-upload validation, `mint_asset_key()`, `verify_upload()`
- `services/api/app/repo/b2_upload.py` — `generate_presigned_upload()` (size + type signed in)
- `services/api/app/service/ingest.py` — `ingest_asset()` fan-out (see [ML pipeline](ml-pipeline.md))

## Canonical Files
- Upload service: `services/api/app/service/upload.py`

## Inputs
- A photo/video file: `image/jpeg|png|gif|webp` or `video/mp4|quicktime|webm`, ≤ 100 MB
- Presign declares `filename`, `content_type`, `size_bytes`; verify sends `key` + `original_filename`

## Outputs
- Original at `library/<user>/<YYYY>/<MM>/<asset_id>.<ext>`
- Derivatives (thumbnails, EXIF sidecar, optional CLIP embedding + tags) via ingest
- `FileUploadResponse` (key, filename, size, type)

## Flow
- Presign: validate the declared file, mint an opaque `library/` key + `asset_id`, sign a short-lived PUT (size + content-type bound into the URL).
- Browser PUTs the bytes straight to B2 (no bytes through the API → Vercel's 4.5 MB limit doesn't apply).
- Verify: HEAD for size/type, Range-GET magic-byte sniff for signatured types, then `ingest_asset()` fans out derivatives and writes the sidecar. The user's real filename is preserved in the sidecar.

## Edge Cases
- Disallowed type / extension mismatch → 415 at presign.
- Oversize / empty → 413 / 400.
- Signature mismatch on verify → object deleted, 415.
- Key outside `library/` → rejected.
- Missing object on verify → 404.

## UX States
- Dropzone idle / drag-active / disabled (queue running).
- Per-file progress; server-side phase while verify + ingest run.

## Verification
- Test files: `services/api/tests/test_upload_validation.py`, `services/api/tests/test_upload_conflict.py`, `apps/web/src/lib/upload-file-types.test.ts`
- Required cases: presign validation, key minting, verify→ingest wiring, signature reject/delete, prefix guard
- Focused verify command: `services/api/.venv/bin/python -m pytest tests/test_upload_validation.py`
- Default pre-PR verify command: `pnpm verify`
- Pass criteria: focused tests and `pnpm verify` green

## Related Docs
- [ML pipeline](ml-pipeline.md)
- [Metadata / EXIF sidecar](metadata-extraction.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
