import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "./StatusBadge";
import { CostDisplay } from "./CostDisplay";
import { mediaUrl } from "@/lib/api";
import { relativeTime, stepLabel } from "@/lib/utils";
import type { RunSummary } from "@/types";

export function ReelCard({ run, index }: { run: RunSummary; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, delay: Math.min(index, 8) * 0.05 }}
    >
      <Link
        to={`/run/${run.run_id}`}
        className="group block overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/40 transition-all hover:border-zinc-700 hover:shadow-lg hover:shadow-black/30"
      >
        <div className="relative aspect-[9/16] w-full overflow-hidden bg-zinc-950">
          {run.status === "done" && run.has_video ? (
            <video
              src={mediaUrl(run.run_id, "video.mp4")}
              preload="metadata"
              muted
              playsInline
              controls
              className="size-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
            />
          ) : run.status === "failed" ? (
            <div className="flex size-full flex-col items-center justify-center gap-2 p-4 text-center">
              <span className="text-xs text-rose-300">Fallo en el pipeline</span>
              {run.error && (
                <span className="line-clamp-3 text-[11px] text-zinc-500">{run.error}</span>
              )}
            </div>
          ) : (
            <div className="flex size-full flex-col items-center justify-center gap-3 p-4 text-center">
              <Loader2 className="size-6 animate-spin text-violet-400" />
              <span className="text-xs text-zinc-300">{stepLabel(run.current_step)}</span>
            </div>
          )}
        </div>
        <div className="flex flex-col gap-2 p-3.5">
          <p className="line-clamp-2 text-sm font-medium leading-snug text-zinc-100">
            {run.topic}
          </p>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <StatusBadge status={run.status} />
              {run.provider && (
                <Badge variant="outline" className="text-[10px] uppercase">
                  {run.provider}
                </Badge>
              )}
            </div>
            <CostDisplay credits={run.cost_credits} />
          </div>
          <span className="mono text-[10px] text-zinc-600">
            {relativeTime(run.created_at)}
          </span>
        </div>
      </Link>
    </motion.div>
  );
}
