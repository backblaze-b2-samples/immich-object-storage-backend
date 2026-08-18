"use client";

import Image from "next/image";
import { Film, ImageIcon, Star } from "lucide-react";

import type { AssetSummary } from "@immich-object-storage-backend/shared";
import { useAssetThumbnailUrl } from "@/lib/queries";
import { MlStatusBadge } from "./ml-status-badge";

/**
 * One photo in the gallery grid. The thumbnail is a presigned GET against the
 * asset's `thumbs/<id>/thumbnail.webp`; a video (or an image whose thumbnail
 * wasn't generated) falls back to an icon placeholder.
 */
export function AssetCard({
  asset,
  score,
  onOpen,
}: {
  asset: AssetSummary;
  score?: number;
  onOpen: (assetId: string) => void;
}) {
  const hasThumb = asset.is_image && !!asset.thumbnail_key;
  const { data } = useAssetThumbnailUrl(asset.asset_id, "thumbnail", hasThumb);

  return (
    <button
      type="button"
      onClick={() => onOpen(asset.asset_id)}
      className="group relative flex flex-col overflow-hidden rounded-lg border border-border bg-card text-left transition-colors hover:border-primary/60"
    >
      <div className="relative aspect-square w-full overflow-hidden bg-muted">
        {data?.url ? (
          <Image
            src={data.url}
            alt={asset.original_filename}
            fill
            sizes="(max-width: 768px) 45vw, 220px"
            className="object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            unoptimized
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-muted-foreground">
            {asset.is_image ? (
              <ImageIcon className="h-8 w-8" aria-hidden="true" />
            ) : (
              <Film className="h-8 w-8" aria-hidden="true" />
            )}
          </div>
        )}
        {asset.favorite && (
          <span className="absolute right-2 top-2 rounded-full bg-background/80 p-1 text-amber-500 shadow-sm">
            <Star className="h-3.5 w-3.5 fill-current" aria-label="Favorite" />
          </span>
        )}
        {score !== undefined && (
          <span className="absolute left-2 top-2 rounded bg-background/85 px-1.5 py-0.5 font-mono text-[10px] tabular-nums text-foreground shadow-sm">
            {score.toFixed(3)}
          </span>
        )}
      </div>
      <div className="flex items-center justify-between gap-2 px-2.5 py-2">
        <span className="truncate text-xs font-medium" title={asset.original_filename}>
          {asset.original_filename}
        </span>
        <MlStatusBadge status={asset.ml_status} />
      </div>
    </button>
  );
}
