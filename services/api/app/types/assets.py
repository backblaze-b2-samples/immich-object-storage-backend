"""Boundary models for the photo-library surface.

An `Asset` is one photo. B2 is the source of truth: every asset is reconstructed
from its `sidecar/<asset_id>.json`, which points at the original plus every
derivative (thumbnails, CLIP embedding, smart tags). `ml_status` reflects the
optional on-device CLIP layer:

- ``done``        — embedding + smart tags were computed and stored
- ``pending``     — asset ingested, ML not run yet
- ``failed``      — ML deps present but inference raised
- ``unavailable`` — ML deps (torch / open_clip) are not installed
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

MLStatus = Literal["done", "pending", "failed", "unavailable"]


class SmartTag(BaseModel):
    label: str
    score: float


class AssetSummary(BaseModel):
    """Gallery-card view of one photo."""

    asset_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    size_human: str
    uploaded_at: datetime
    favorite: bool = False
    tags: list[str] = Field(default_factory=list)
    ml_status: MLStatus = "pending"
    original_key: str
    thumbnail_key: str | None = None
    is_image: bool = True


class AssetDetail(AssetSummary):
    """Full asset view for the detail panel."""

    description: str = ""
    exif: dict | None = None
    image_width: int | None = None
    image_height: int | None = None
    smart_tags: list[SmartTag] = Field(default_factory=list)
    embedding_model: str | None = None
    embedding_dim: int | None = None
    ml_message: str | None = None
    # Every B2 object this asset owns: original + derivatives, keyed by role.
    derivative_keys: dict[str, str] = Field(default_factory=dict)


class AssetUpdate(BaseModel):
    """Editable metadata. All fields optional — only provided ones are written.

    `tags` is free text (an open, genuinely-unbounded vocabulary), which is why
    it is a token list and not a fixed-choice selector.
    """

    description: str | None = None
    favorite: bool | None = None
    tags: list[str] | None = None


class AssetUpdateRequest(AssetUpdate):
    """Edit request body: which asset, plus the fields to change."""

    asset_id: str


class AssetIdRequest(BaseModel):
    asset_id: str


class AssetActionResponse(BaseModel):
    asset_id: str
    deleted: bool = False


class SearchMatch(BaseModel):
    asset: AssetSummary
    score: float


class SearchResponse(BaseModel):
    query: str
    # ``ok`` when CLIP produced a query embedding and ranked the library;
    # ``unavailable`` when the optional ML layer is not installed (or failed) —
    # the message then tells the user how to enable it.
    ml_status: Literal["ok", "unavailable"]
    message: str | None = None
    results: list[SearchMatch] = Field(default_factory=list)


class LibraryStats(BaseModel):
    """Dashboard metrics for the photo library."""

    total_assets: int
    original_bytes: int
    derivative_bytes: int
    total_bytes: int
    original_human: str
    derivative_human: str
    total_human: str
    # derived / original — the write-amplification headline (one photo becomes
    # ~2-3x its bytes across originals + thumbnails + ML + sidecars).
    write_amplification: float
    storage_by_prefix: dict[str, int]
    ml_status_counts: dict[str, int]
    favorites: int
