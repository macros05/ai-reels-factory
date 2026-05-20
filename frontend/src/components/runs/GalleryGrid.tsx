import { FilmIcon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { ReelCard } from "./ReelCard";
import type { RunSummary } from "@/types";

export function GalleryGrid({
  runs,
  loading,
}: {
  runs: RunSummary[] | undefined;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="overflow-hidden rounded-xl border border-zinc-800">
            <Skeleton className="aspect-[9/16] w-full rounded-none" />
            <div className="space-y-2 p-3.5">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (!runs || runs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-zinc-800 bg-zinc-900/20 px-6 py-16 text-center">
        <div className="flex size-12 items-center justify-center rounded-full bg-zinc-900 text-zinc-500">
          <FilmIcon className="size-5" />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium text-zinc-200">Aún no has generado ningún reel</p>
          <p className="text-xs text-zinc-500">
            Lanza el primero desde el formulario de arriba.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {runs.map((r, i) => (
        <ReelCard key={r.run_id} run={r} index={i} />
      ))}
    </div>
  );
}
