# Product

## Register

product

## Users

Two audiences: (1) privacy-conscious individuals and self-hosters who want a photo
library they fully own, with unlimited archival capacity on Backblaze B2; and (2) AI
engineers who want a reference for a media pipeline whose storage layer is B2 — photo
ingest, derivative fan-out, on-device ML, and semantic search, all persisting to B2 over
the S3-compatible API. They read the repo to understand the object-storage pattern
Immich uses with an external backend, then adapt it.

## Product Purpose

A self-hosted photo-library backend (Next.js 16 + FastAPI) that stores everything on
Backblaze B2: originals, thumbnails, on-device CLIP embeddings, zero-shot smart tags,
and EXIF sidecars, all under Immich-style structured prefixes. It makes the
write-amplification story concrete (one photo becomes ~2–3× its bytes across originals +
derivatives) and shows B2 as the single source of truth for an entire media library.
The headline capability — CLIP semantic search + smart tags — uses Immich's own default
model (OpenCLIP `ViT-B-32`/`openai`), packaged as an optional, separately-installed
layer just as Immich ships ML in a separate container. Success = a builder can clone it,
run it, add a photo, watch it fan out to B2, and search it by meaning.

## Maturity and Support Boundary

This is a maintained open-source sample, not a complete hosted photo service. It is
built with production-minded controls and can be adapted with caution, but adopters own
product-specific validation, security, deployment, and operations (it is single-tenant
and unauthenticated by design). Repository defects and feature requests go through the
public GitHub issue tracker; B2 account, billing, service, and API questions go through
Backblaze Support. The sample itself is not covered by the Backblaze service level
agreement, and no SLA is provided for the repository software.

## Brand Personality

Confident, precise, quietly professional. Voice is direct and free of hype ("Stop
wiring boilerplate and start building"). The interface should feel like a modern
developer tool — considered, calm, trustworthy — not a marketing showpiece. It is a
**neutral foundation** that others rebrand: the design carries craft through restraint,
not through a strong opinionated identity of its own.

## Anti-references

- **Generic AI/SaaS slop.** No gradient text, hero-metric templates, identical
  icon-card grids, tracked uppercase eyebrows, or decorative glassmorphism. These are
  the exact 2026 AI tells this kit exists to help builders avoid.
- **Over-branded / loud.** No heavy brand-color drenching, decorative motion, or flashy
  effects. It is scaffolding to be rebranded, not a hero page.
- **Toy / prototype feel.** No missing states, inconsistent components, or placeholder
  polish. Must read as polished, dependable scaffolding.
- **Enterprise-drab.** No Bootstrap-era gray boxes or dense-but-lifeless admin-panel
  look. Considered, like modern dev tools (Linear, GitHub Primer, Stripe).

## Design Principles

- **Practice what you preach.** The kit itself must model the engineering quality it
  asks agents to produce. Slop here propagates into every project built on it.
- **Neutral foundation, easy to rebrand.** Identity lives in tokens (`globals.css`) and
  one config file. Screens are built from the shared UI kit so a rebrand is a token
  swap, not a rewrite.
- **Earned familiarity over novelty.** Use standard, trusted affordances (top bar +
  side nav, command palette, data tables). The tool disappears into the task.
- **Every state is designed.** Default, hover, focus, active, disabled, loading (skeleton),
  empty (teaches the interface), and error (says what's wrong + offers retry) — never
  half-shipped.
- **Consistency is the feature.** One button vocabulary, one form-control set, one icon
  style across every screen. Divergence is a bug.

## Accessibility & Inclusion

Target **WCAG 2.1 AA**. Body text ≥ 4.5:1, large/bold text ≥ 3:1, visible focus
indicators on every interactive element, full keyboard navigation, correct semantic
landmarks and heading order, labelled form controls, and a `prefers-reduced-motion`
alternative for every animation. Full light and dark theme parity.
