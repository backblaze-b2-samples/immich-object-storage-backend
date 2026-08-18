"use client";

import { useState } from "react";
import { Search as SearchIcon, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { EmptyState } from "@/components/ui/empty-state";
import { useSearch } from "@/lib/queries";
import { AssetCard } from "@/components/library/asset-card";
import { AssetDetailDialog } from "@/components/library/asset-detail-dialog";

const EXAMPLES = ["beach at sunset", "a dog in the snow", "city street at night"];

export function SearchView() {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const { data, isFetching, error, refetch } = useSearch(query, query.length > 0);

  const submit = (value: string) => {
    setInput(value);
    setQuery(value.trim());
  };

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(input);
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe what you're looking for — e.g. “beach at sunset”"
            className="pl-9"
            aria-label="Semantic search query"
          />
        </div>
        <Button type="submit" disabled={!input.trim()}>
          Search
        </Button>
      </form>

      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => submit(ex)}
            className="rounded-full border border-border px-2.5 py-1 hover:border-primary/60"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <ErrorState error={error} onRetry={() => refetch()} />}

      {isFetching && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="aspect-square w-full rounded-lg" />
          ))}
        </div>
      )}

      {data && !isFetching && data.ml_status === "unavailable" && (
        <Alert>
          <Sparkles />
          <AlertTitle>Semantic search needs the optional CLIP layer</AlertTitle>
          <AlertDescription>{data.message}</AlertDescription>
        </Alert>
      )}

      {data && !isFetching && data.ml_status === "ok" && data.message && (
        <Alert>
          <Sparkles />
          <AlertTitle>No results yet</AlertTitle>
          <AlertDescription>{data.message}</AlertDescription>
        </Alert>
      )}

      {data && !isFetching && data.ml_status === "ok" && data.results.length > 0 && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {data.results.map((match) => (
            <AssetCard
              key={match.asset.asset_id}
              asset={match.asset}
              score={match.score}
              onOpen={setSelected}
            />
          ))}
        </div>
      )}

      {data &&
        !isFetching &&
        data.ml_status === "ok" &&
        !data.message &&
        data.results.length === 0 && (
          <EmptyState
            icon={SearchIcon}
            title="No matches"
            description="No photos scored close enough to this query. Try different words."
          />
        )}

      <AssetDetailDialog assetId={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
