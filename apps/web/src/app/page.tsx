import Link from "next/link";
import { Search, Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LibraryOverview } from "@/components/dashboard/library-overview";

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Your photo library on Backblaze B2 — assets, storage fan-out, and ML
            status.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline" className="h-8">
            <Link href="/search">
              <Search className="h-3.5 w-3.5" />
              Search
            </Link>
          </Button>
          <Button asChild size="sm" className="h-8">
            <Link href="/upload">
              <Upload className="h-3.5 w-3.5" />
              Add photos
            </Link>
          </Button>
        </div>
      </div>
      <LibraryOverview />
    </div>
  );
}
