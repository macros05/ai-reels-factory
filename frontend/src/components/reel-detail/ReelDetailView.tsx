import { Copy, Download } from "lucide-react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ReelPlayer } from "@/components/runs/ReelPlayer";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { CaptionEditor } from "./CaptionEditor";
import { HashtagChips } from "./HashtagChips";
import { mediaUrl } from "@/lib/api";
import { formatCredits, formatDate } from "@/lib/utils";
import type { RunDetail } from "@/types";

export function ReelDetailView({ run }: { run: RunDetail }) {
  const hashtags = run.script?.hashtags ?? [];
  const caption = run.caption ?? "";

  async function copyFull() {
    const tagLine = hashtags.map((h) => `#${h.replace(/^#/, "")}`).join(" ");
    const body = run.script?.caption ?? "";
    await navigator.clipboard.writeText(`${body}\n\n${tagLine}`.trim());
    toast.success("Caption + hashtags copiados");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]"
    >
      <div className="min-w-0">
        {run.status === "done" && run.has_video ? (
          <ReelPlayer runId={run.run_id} />
        ) : (
          <div className="flex aspect-[9/16] items-center justify-center rounded-xl border border-zinc-800 bg-zinc-900/40 text-sm text-zinc-400">
            {run.status === "failed" ? "Pipeline falló" : "Generando…"}
          </div>
        )}
      </div>

      <div className="flex min-w-0 flex-col gap-5">
        <div className="flex flex-col gap-2">
          <h2 className="text-xl font-semibold tracking-tight text-zinc-100">{run.topic}</h2>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={run.status} />
            {run.provider && (
              <Badge variant="outline" className="uppercase">
                {run.provider}
              </Badge>
            )}
          </div>
        </div>

        <Card>
          <CardContent className="grid grid-cols-2 gap-4 p-4 text-xs">
            <Field label="Coste" value={<span className="mono">{formatCredits(run.cost_credits)}</span>} />
            <Field
              label="Proveedor"
              value={<span className="uppercase">{run.provider ?? "—"}</span>}
            />
            <Field
              label="Run ID"
              value={<span className="mono break-all">{run.run_id}</span>}
            />
            <Field label="Creado" value={formatDate(run.created_at)} />
          </CardContent>
        </Card>

        {run.status === "done" && (
          <>
            <CaptionEditor caption={caption} />
            <HashtagChips hashtags={hashtags} />
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button asChild variant="default" className="flex-1">
                <a href={mediaUrl(run.run_id, "video.mp4")} download={`${run.run_id}.mp4`}>
                  <Download className="size-4" />
                  Descargar MP4
                </a>
              </Button>
              <Button variant="secondary" className="flex-1" onClick={copyFull}>
                <Copy className="size-4" />
                Copiar caption completo
              </Button>
            </div>
          </>
        )}

        {run.status === "failed" && run.error && (
          <div className="rounded-md border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-200">
            {run.error}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wide text-zinc-500">{label}</span>
      <span className="text-zinc-200">{value}</span>
    </div>
  );
}
