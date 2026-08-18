import { UploadForm } from "@/components/upload/upload-form";

export default function UploadPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Add photos to your library</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground text-pretty">
          Drag photos in or click to browse. Each upload goes straight to
          Backblaze B2, then fans out into thumbnails, an EXIF sidecar, and — if
          the optional ML layer is installed — a CLIP embedding and smart tags.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <UploadForm />
      </div>
    </div>
  );
}
