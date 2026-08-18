import { Badge } from "@/components/ui/badge";
import type { MLStatus } from "@immich-object-storage-backend/shared";

const LABELS: Record<MLStatus, string> = {
  done: "AI tagged",
  pending: "ML pending",
  failed: "ML failed",
  unavailable: "ML off",
};

const VARIANTS: Record<
  MLStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  done: "secondary",
  pending: "outline",
  failed: "destructive",
  unavailable: "outline",
};

export function MlStatusBadge({ status }: { status: MLStatus }) {
  return (
    <Badge variant={VARIANTS[status]} className="text-[10px]">
      {LABELS[status]}
    </Badge>
  );
}
