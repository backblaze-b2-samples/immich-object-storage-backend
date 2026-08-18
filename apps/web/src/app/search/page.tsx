import { SearchView } from "@/components/search/search-view";

export default function SearchPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Semantic search</h1>
        <p className="mt-1.5 max-w-prose text-sm text-muted-foreground text-pretty">
          Search your photos by meaning, not filename. Your query is embedded
          with the same on-device CLIP model (ViT-B-32/openai) that indexed each
          photo at ingest, then cosine-ranked against the embeddings stored in
          B2.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <SearchView />
      </div>
    </div>
  );
}
