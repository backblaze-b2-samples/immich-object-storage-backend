<!-- last_verified: 2026-08-06 -->
# App Workflows

User journeys inside the application.

## Add Photos (create)

- User navigates to `/upload`
- Drops or selects photos/videos in the dropzone (JPEG/PNG/GIF/WEBP, MP4/MOV/WEBM, max 100MB)
- Each original uploads **directly from the browser to B2** (a presigned PUT). A determinate bar tracks the bytes leaving the browser; once sent, the row switches to an indeterminate "Verifying upload…" phase while the API verifies the object **and runs the ingest fan-out** (thumbnails + EXIF sidecar + optional CLIP embedding/tags)
- On success: toast + green checkmark; the photo now appears under **Library**
- On failure: red status icon with error message
- The queue lives in an app-wide provider (survives navigation); reload mid-upload asks for confirmation
- See: [Photo Ingest](features/file-upload.md), [ML Pipeline](features/ml-pipeline.md)

## Browse and Manage the Library (read / edit / run / delete)

- User navigates to `/library` — a thumbnail grid of the app's own photos (the `library/` prefix), reconstructed from the sidecars
- Clicking a photo opens the asset-detail dialog: the presigned original, dimensions/size, EXIF, ML status, embedding model, and smart-tag badges
- **Edit**: change description (textarea), favorite (switch), and your own tags (comma-separated free text) → Save rewrites the sidecar on B2
- **Re-run ML**: regenerates thumbnails + embedding + smart tags, preserving your edits
- **Delete**: a confirm dialog, then a cascade delete of the original and every derivative from B2
- Empty state: "Your library is empty" with an Add-photos CTA
- See: [Photo Library](features/photo-library.md)

## Semantic Search

- User navigates to `/search` and types a description ("beach at sunset"), or clicks an example chip
- The query is embedded with the same CLIP model that indexed each photo, then cosine-ranked against the embeddings stored in B2; matches render as a scored thumbnail grid, each opening the same asset-detail dialog
- If the optional ML layer isn't installed (or no embeddings exist yet), an informational alert explains how to enable it — the search never errors
- See: [Semantic Search](features/semantic-search.md)

## Browse the Full Bucket

- User navigates to `/files` — the retained full-bucket explorer that browses **every** prefix (`library/ thumbs/ ml/ sidecar/`), not just the library
- Tree view with preview, download, and delete per object; a per-row actions menu on every viewport
- See: [File Browser](features/file-browser.md)

The full-bucket explorer keeps all of the starter's behaviors (tree view,
`?preview=<key>` deep links from ⌘K, inline preview, download, and a held
"Deleting…" confirm dialog); see [File Browser](features/file-browser.md).

## View Dashboard

- User navigates to `/` (home)
- One API call loads `GET /assets/stats`
- Stat cards show: photos, total on B2, write-amplification ratio, favorites
- A storage-by-prefix bar chart shows how the total splits across `library/`, `thumbs/`, `ml/`, and `sidecar/` — making the write-amplification story concrete
- An ML-status breakdown counts assets by `done` / `pending` / `failed` / `unavailable`
- Empty state: zeros and a `0×` amplification, no crash
- See: [Dashboard](features/dashboard.md)

## Change Preferences

- User navigates to `/settings`
- A banner at the top states that the page is mostly a demonstration: only Theme is wired up for real, the rest showcases what a settings page can look like when you adapt the kit
- **Theme** (real): editing it and saving applies it immediately and persists it (`next-themes`), and the header's theme toggle drives the same state
- **Profile and preference fields** (demo): Display name, Bio, Default file view (Tree/List/Grid), Email me on every upload, Warn me when approaching quota + threshold. Each is labelled "Demo field", persists to `localStorage` only, and drives no behaviour — there is no account system, mailer, quota banner, activity log, or List/Grid view behind them yet
- Saving reports honestly: a success toast that separates the real theme change from the locally-stored demo values, or a warning toast if the browser blocked storage (theme still changes). It never claims a save that did not happen — the original page toasted "Settings saved" for fields that changed nothing
- Danger Zone actions are a demo — no real delete runs
- See: [Settings](features/settings.md)
