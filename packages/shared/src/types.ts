export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  /** Set when a format-specific extractor was skipped or failed (e.g. an image
   *  above the decompression-bomb decode limit). Core fields stay exact. */
  metadata_warning: string | null;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

/** A short-lived presigned PUT the browser uploads a file directly to B2 with.
 *  `headers` are signed into the URL, so the browser must send them verbatim.
 *  `key` is a minted `library/<user>/<YYYY>/<MM>/<asset_id>.<ext>` path. */
export interface PresignUploadResponse {
  key: string;
  asset_id: string;
  url: string;
  method: string;
  content_type: string;
  headers: Record<string, string>;
  expires_in: number;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Photo library (Asset) --------------------------------------------------

export type MLStatus = "done" | "pending" | "failed" | "unavailable";

export interface SmartTag {
  label: string;
  score: number;
}

export interface AssetSummary {
  asset_id: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  size_human: string;
  uploaded_at: string;
  favorite: boolean;
  tags: string[];
  ml_status: MLStatus;
  original_key: string;
  thumbnail_key: string | null;
  is_image: boolean;
}

export interface AssetDetail extends AssetSummary {
  description: string;
  exif: Record<string, string> | null;
  image_width: number | null;
  image_height: number | null;
  smart_tags: SmartTag[];
  embedding_model: string | null;
  embedding_dim: number | null;
  ml_message: string | null;
  derivative_keys: Record<string, string>;
}

export interface AssetUpdate {
  description?: string | null;
  favorite?: boolean | null;
  tags?: string[] | null;
}

export interface SearchMatch {
  asset: AssetSummary;
  score: number;
}

export interface SearchResponse {
  query: string;
  ml_status: "ok" | "unavailable";
  message: string | null;
  results: SearchMatch[];
}

export interface LibraryStats {
  total_assets: number;
  original_bytes: number;
  derivative_bytes: number;
  total_bytes: number;
  original_human: string;
  derivative_human: string;
  total_human: string;
  write_amplification: number;
  storage_by_prefix: Record<string, number>;
  ml_status_counts: Record<string, number>;
  favorites: number;
}
