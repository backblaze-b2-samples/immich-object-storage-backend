"use client";

import { useEffect } from "react";
import Image from "next/image";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { RefreshCw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/error-state";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import {
  useAsset,
  useAssetOriginalUrl,
  useDeleteAsset,
  useRerunAssetMl,
  useUpdateAsset,
} from "@/lib/queries";
import { MlStatusBadge } from "./ml-status-badge";

const editSchema = z.object({
  description: z.string().max(2000).optional(),
  favorite: z.boolean(),
  // Free text on purpose: tags are an open, unbounded vocabulary, so a selector
  // would be wrong here (see docs/features/photo-library.md). Comma-separated.
  tags: z.string().max(500).optional(),
});

type EditValues = z.infer<typeof editSchema>;

export function AssetDetailDialog({
  assetId,
  onClose,
}: {
  assetId: string | null;
  onClose: () => void;
}) {
  const open = assetId !== null;
  const { data: asset, isLoading, error, refetch } = useAsset(
    assetId ?? undefined,
    open
  );
  const { data: original } = useAssetOriginalUrl(
    assetId ?? undefined,
    open && !!asset?.is_image
  );
  const update = useUpdateAsset();
  const rerun = useRerunAssetMl();
  const remove = useDeleteAsset();

  const form = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: { description: "", favorite: false, tags: "" },
  });

  useEffect(() => {
    if (asset) {
      form.reset({
        description: asset.description ?? "",
        favorite: asset.favorite,
        tags: asset.tags.join(", "),
      });
    }
  }, [asset, form]);

  const onSubmit = (values: EditValues) => {
    if (!assetId) return;
    const tags = (values.tags ?? "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    update.mutate(
      { assetId, update: { description: values.description ?? "", favorite: values.favorite, tags } },
      {
        onSuccess: () => toast.success("Metadata saved to the sidecar on B2"),
        onError: (e) => toast.error(`Save failed: ${e.message}`),
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[90svh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="truncate">
            {asset?.original_filename ?? "Asset"}
          </DialogTitle>
          <DialogDescription>
            Original, thumbnails, embedding, smart tags and EXIF sidecar all live
            on Backblaze B2 under this asset&apos;s prefixes.
          </DialogDescription>
        </DialogHeader>

        {isLoading && <Skeleton className="h-64 w-full" />}
        {error && <ErrorState error={error} onRetry={() => refetch()} />}

        {asset && (
          <div className="space-y-5">
            <div className="relative h-[min(45svh,360px)] w-full overflow-hidden rounded-md bg-muted">
              {asset.is_image && original?.url ? (
                <Image
                  src={original.url}
                  alt={asset.original_filename}
                  fill
                  sizes="(max-width: 768px) 100vw, 700px"
                  className="object-contain"
                  unoptimized
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
                  {asset.is_image ? "Loading original…" : "Video original stored on B2"}
                </div>
              )}
            </div>

            {/* ML state + smart tags */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <MlStatusBadge status={asset.ml_status} />
                {asset.embedding_model && (
                  <span className="text-xs text-muted-foreground">
                    {asset.embedding_model} · {asset.embedding_dim}-dim embedding
                  </span>
                )}
              </div>
              {asset.ml_message && (
                <p className="text-xs text-muted-foreground">{asset.ml_message}</p>
              )}
              {asset.smart_tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {asset.smart_tags.map((t) => (
                    <Badge key={t.label} variant="outline" className="text-[11px]">
                      {t.label} · {(t.score * 100).toFixed(0)}%
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <AssetFacts asset={asset} />

            {/* Edit metadata (edit verb) */}
            <Form {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4 border-t border-border pt-4">
                <FormField
                  control={form.control}
                  name="description"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Description</FormLabel>
                      <FormControl>
                        <Textarea
                          className="resize-none"
                          placeholder="Add a caption or notes for this photo"
                          {...field}
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="tags"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Your tags</FormLabel>
                      <FormControl>
                        <Input placeholder="beach, family, 2026" {...field} />
                      </FormControl>
                      <FormDescription>
                        Comma-separated. These are your own labels, separate from
                        the AI smart tags above.
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={form.control}
                  name="favorite"
                  render={({ field }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-md border border-border p-3">
                      <FormLabel>Favorite</FormLabel>
                      <FormControl>
                        <Switch checked={field.value} onCheckedChange={field.onChange} />
                      </FormControl>
                    </FormItem>
                  )}
                />

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={rerun.isPending}
                      onClick={() =>
                        assetId &&
                        rerun.mutate(assetId, {
                          onSuccess: () => toast.success("ML re-run complete"),
                          onError: (e) => toast.error(`Re-run failed: ${e.message}`),
                        })
                      }
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${rerun.isPending ? "animate-spin" : ""}`} />
                      Re-run ML processing
                    </Button>

                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button type="button" variant="destructive" size="sm">
                          <Trash2 className="h-3.5 w-3.5" />
                          Delete
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>Delete this photo?</AlertDialogTitle>
                          <AlertDialogDescription>
                            This removes the original and every derivative
                            (thumbnails, embedding, smart tags, sidecar) from B2.
                            This cannot be undone.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Cancel</AlertDialogCancel>
                          <AlertDialogAction
                            onClick={() =>
                              assetId &&
                              remove.mutate(assetId, {
                                onSuccess: () => {
                                  toast.success("Asset and derivatives deleted from B2");
                                  onClose();
                                },
                                onError: (e) => toast.error(`Delete failed: ${e.message}`),
                              })
                            }
                          >
                            Delete
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                  </div>

                  <Button type="submit" size="sm" disabled={update.isPending}>
                    {update.isPending ? "Saving…" : "Save metadata"}
                  </Button>
                </div>
              </form>
            </Form>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function AssetFacts({
  asset,
}: {
  asset: NonNullable<ReturnType<typeof useAsset>["data"]>;
}) {
  const facts: [string, string][] = [
    ["Size", asset.size_human],
    ["Type", asset.content_type],
    [
      "Dimensions",
      asset.image_width && asset.image_height
        ? `${asset.image_width}×${asset.image_height}`
        : "—",
    ],
    ["Uploaded", new Date(asset.uploaded_at).toLocaleString()],
    ["Original key", asset.original_key],
  ];
  const exifEntries = Object.entries(asset.exif ?? {}).slice(0, 6);

  return (
    <div className="grid gap-4 border-t border-border pt-4 sm:grid-cols-2">
      <dl className="space-y-1 text-xs">
        {facts.map(([k, v]) => (
          <div key={k} className="flex gap-2">
            <dt className="w-24 shrink-0 text-muted-foreground">{k}</dt>
            <dd className="truncate font-mono" title={v}>
              {v}
            </dd>
          </div>
        ))}
      </dl>
      {exifEntries.length > 0 && (
        <dl className="space-y-1 text-xs">
          <p className="mb-1 font-medium text-muted-foreground">EXIF</p>
          {exifEntries.map(([k, v]) => (
            <div key={k} className="flex gap-2">
              <dt className="w-24 shrink-0 text-muted-foreground">{k}</dt>
              <dd className="truncate font-mono" title={String(v)}>
                {String(v)}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}
