/**
 * Client-side allow-list for the dropzone, mirroring the backend's
 * `ALLOWED_TYPES` / `MIME_EXTENSION_MAP` in
 * `services/api/app/service/upload.py`. This is a photo library, so the upload
 * surface accepts images and video only (the full-bucket /files explorer can
 * still browse anything already in the bucket). The server re-validates every
 * upload — this just gives instant feedback and filters the OS file picker.
 * Keep the two in sync when adding or removing a type.
 *
 * Shape matches react-dropzone's `accept`: MIME type → matching extensions.
 */
export const ACCEPTED_FILE_TYPES: Record<string, string[]> = {
  "image/jpeg": [".jpg", ".jpeg", ".jfif"],
  "image/png": [".png"],
  "image/gif": [".gif"],
  "image/webp": [".webp"],
  "video/mp4": [".mp4"],
  "video/quicktime": [".mov"],
  "video/webm": [".webm"],
};
