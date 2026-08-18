"use client";

import { useState } from "react";
import Link from "next/link";
import { ImageIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { useAssets } from "@/lib/queries";
import { AssetCard } from "./asset-card";
import { AssetDetailDialog } from "./asset-detail-dialog";

/**
 * The sample-scoped asset explorer: a thumbnail grid of the app's own photos
 * (everything under the `library/` prefix), reconstructed from the sidecars.
 * The full-bucket `/files` explorer still browses every prefix.
 */
export function LibraryGallery() {
  const { data: assets, isLoading, error, refetch } = useAssets();
  const [selected, setSelected] = useState<string | null>(null);

  if (error) {
    return <ErrorState error={error} onRetry={() => refetch()} />;
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="aspect-square w-full rounded-lg" />
        ))}
      </div>
    );
  }

  if (!assets || assets.length === 0) {
    return (
      <EmptyState
        icon={ImageIcon}
        title="Your library is empty"
        description="Add photos to see them ingested to B2 with thumbnails, an EXIF sidecar, and — with the ML layer installed — a CLIP embedding and smart tags."
        action={
          <Button asChild size="sm">
            <Link href="/upload">Add photos</Link>
          </Button>
        }
      />
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {assets.map((asset) => (
          <AssetCard key={asset.asset_id} asset={asset} onOpen={setSelected} />
        ))}
      </div>
      <AssetDetailDialog assetId={selected} onClose={() => setSelected(null)} />
    </>
  );
}
