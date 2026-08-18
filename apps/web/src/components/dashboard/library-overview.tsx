"use client";

import { HardDrive, ImageIcon, Layers, Star } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import { LoadingNotice } from "@/components/common/loading-notice";
import { useLibraryStats } from "@/lib/queries";

const PREFIX_LABELS: Record<string, string> = {
  originals: "library/ (originals)",
  thumbnails: "thumbs/ (previews)",
  ml: "ml/ (embeddings + tags)",
  sidecars: "sidecar/ (metadata)",
};

function humanize(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function LibraryOverview() {
  const { data: stats, isLoading, error, refetch } = useLibraryStats();

  if (error) {
    return (
      <Card>
        <CardContent className="p-0">
          <ErrorState error={error} onRetry={() => refetch()} />
        </CardContent>
      </Card>
    );
  }

  const cards = [
    { title: "Photos", value: stats?.total_assets ?? 0, icon: ImageIcon },
    { title: "Total on B2", value: stats?.total_human ?? "0 B", icon: HardDrive },
    {
      title: "Write amplification",
      value: stats ? `${stats.write_amplification.toFixed(2)}×` : "—",
      icon: Layers,
    },
    { title: "Favorites", value: stats?.favorites ?? 0, icon: Star },
  ];

  const totalBytes = stats?.total_bytes ?? 0;
  const prefixEntries = Object.entries(stats?.storage_by_prefix ?? {});
  const mlEntries = Object.entries(stats?.ml_status_counts ?? {});

  return (
    <div className="space-y-8">
      {isLoading && <LoadingNotice className="mb-3" subject="library stats" />}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((card, i) => (
          <Card key={card.title} className={`card-hover animate-fade-in-up stagger-${i + 1}`}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pb-2 pt-4">
              <CardTitle className="text-xs font-semibold text-muted-foreground">
                {card.title}
              </CardTitle>
              <div className="stat-icon-wrap">
                <card.icon className="h-4 w-4" />
              </div>
            </CardHeader>
            <CardContent className="px-4 pb-5">
              {isLoading ? (
                <Skeleton className="h-8 w-24" />
              ) : (
                <div className="stat-value">{card.value}</div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="animate-fade-in-up stagger-3">
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">Storage by prefix</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            <p className="text-xs text-muted-foreground">
              One uploaded photo fans out into originals, thumbnails, ML
              artifacts and a metadata sidecar — the write-amplification story,
              all on B2.
            </p>
            {isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              prefixEntries.map(([key, bytes]) => {
                const pct = totalBytes > 0 ? (bytes / totalBytes) * 100 : 0;
                return (
                  <div key={key} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-muted-foreground">
                        {PREFIX_LABELS[key] ?? key}
                      </span>
                      <span className="font-mono tabular-nums">{humanize(bytes)}</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card className="animate-fade-in-up stagger-4">
          <CardHeader className="border-b border-border px-5 py-4">
            <CardTitle className="card-title">ML status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 p-5">
            <p className="text-xs text-muted-foreground">
              Counts of assets by CLIP status. The core B2 pipeline always runs;
              embeddings and smart tags need the optional ML layer.
            </p>
            {isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : mlEntries.length === 0 ? (
              <p className="text-sm text-muted-foreground">No assets yet.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {mlEntries.map(([status, count]) => (
                  <li key={status} className="flex items-center justify-between">
                    <span className="capitalize text-muted-foreground">{status}</span>
                    <span className="font-mono tabular-nums">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
