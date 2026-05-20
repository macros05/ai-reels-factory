import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Header } from "@/components/layout/Header";
import { ReelDetailView } from "@/components/reel-detail/ReelDetailView";
import { Skeleton } from "@/components/ui/skeleton";
import { useRun } from "@/hooks/useRun";

export function ReelDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: run, isLoading, isError } = useRun(id);

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <Link
          to="/"
          className="mb-6 inline-flex items-center gap-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-100"
        >
          <ArrowLeft className="size-4" />
          Volver a la galería
        </Link>

        {isLoading && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
            <Skeleton className="aspect-[9/16] rounded-xl" />
            <div className="flex flex-col gap-3">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-24 rounded-xl" />
              <Skeleton className="h-32 rounded-xl" />
            </div>
          </div>
        )}

        {isError && (
          <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
            No se pudo cargar el run.
          </div>
        )}

        {run && <ReelDetailView run={run} />}
      </main>
    </div>
  );
}
