import { Copy, Download, Film, Tag } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ReelPlayer } from "@/components/runs/ReelPlayer";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { CaptionEditor } from "./CaptionEditor";
import { HashtagChips } from "./HashtagChips";
import { ShotPlanEditor } from "./ShotPlanEditor";
import { mediaUrl } from "@/lib/api";
import { cn, formatCredits, formatDate } from "@/lib/utils";
import type { RunDetail } from "@/types";

type Tab = "overview" | "shot_plan";

export function ReelDetailView({ run }: { run: RunDetail }) {
  const hashtags = run.script?.hashtags ?? [];
  const caption = run.caption ?? "";
  const [tab, setTab] = useState<Tab>("overview");
  const hasPlan = !!run.shot_plan && run.shot_plan.shots.length > 0;

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
      className="flex flex-col gap-6"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]">
        <div className="min-w-0">
          {run.status === "done" && run.has_video ? (
            <ReelPlayer runId={run.run_id} />
          ) : (
            <div className="glass flex aspect-[9/16] items-center justify-center rounded-2xl text-sm text-zinc-400">
              {run.status === "failed" ? "Pipeline falló" : "Generando…"}
            </div>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-5">
          <div className="flex flex-col gap-2">
            <h2 className="text-2xl font-semibold tracking-tight text-zinc-50">
              {run.topic}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge status={run.status} />
              {run.provider && (
                <Badge variant="outline" className="uppercase">
                  {run.provider}
                </Badge>
              )}
              {hasPlan && (
                <Badge
                  variant="outline"
                  className="border-violet-500/30 bg-violet-500/10 text-violet-200 uppercase"
                >
                  <Film className="mr-1 size-3" /> shot plan
                </Badge>
              )}
            </div>
          </div>

          <Card>
            <CardContent className="grid grid-cols-2 gap-4 p-5 text-xs">
              <Field
                label="Coste"
                value={<span className="mono">{formatCredits(run.cost_credits)}</span>}
              />
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
                  <a
                    href={mediaUrl(run.run_id, "video.mp4")}
                    download={`${run.run_id}.mp4`}
                  >
                    <Download className="size-4" />
                    Descargar MP4
                  </a>
                </Button>
                <Button variant="secondary" className="flex-1" onClick={copyFull}>
                  <Copy className="size-4" />
                  Copiar caption + hashtags
                </Button>
              </div>
            </>
          )}

          {run.status === "failed" && run.error && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3.5 text-xs text-rose-200">
              {run.error}
            </div>
          )}
        </div>
      </div>

      {/* Tabs: overview vs shot plan */}
      <div className="flex gap-1 border-b border-white/[0.06]">
        <TabButton active={tab === "overview"} onClick={() => setTab("overview")}>
          <Tag className="size-3.5" /> Resumen
        </TabButton>
        {hasPlan && (
          <TabButton active={tab === "shot_plan"} onClick={() => setTab("shot_plan")}>
            <Film className="size-3.5" /> Shot plan
            <span className="mono ml-1 rounded-full bg-violet-500/15 px-1.5 text-[10px] text-violet-200">
              {run.shot_plan!.shots.length}
            </span>
          </TabButton>
        )}
      </div>

      {tab === "overview" && (
        <OverviewPanel run={run} />
      )}

      {tab === "shot_plan" && hasPlan && (
        <ShotPlanEditor runId={run.run_id} initial={run.shot_plan!} />
      )}
    </motion.div>
  );
}

function OverviewPanel({ run }: { run: RunDetail }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      {run.script && (
        <Card>
          <CardContent className="flex flex-col gap-3 p-5">
            <div className="mono text-[10px] uppercase tracking-wider text-zinc-500">
              Guion
            </div>
            <ScriptLine label="Hook" text={run.script.hook} />
            <ScriptLine label="Body" text={run.script.body} />
            <ScriptLine label="CTA" text={run.script.cta} />
          </CardContent>
        </Card>
      )}
      {run.brief && (
        <Card>
          <CardContent className="flex flex-col gap-3 p-5">
            <div className="mono text-[10px] uppercase tracking-wider text-zinc-500">
              Brief creativo
            </div>
            {run.brief.audience && <BriefRow label="Audiencia" value={run.brief.audience} />}
            {run.brief.tone.length > 0 && (
              <BriefRow label="Tono" value={run.brief.tone.join(" · ")} />
            )}
            {run.brief.mood.length > 0 && (
              <BriefRow label="Mood" value={run.brief.mood.join(" · ")} />
            )}
            {run.brief.visual_vibe.length > 0 && (
              <BriefRow label="Vibra" value={run.brief.visual_vibe.join(" · ")} />
            )}
            {run.brief.palette && <BriefRow label="Paleta" value={run.brief.palette} />}
            {run.brief.cta_goal && <BriefRow label="CTA goal" value={run.brief.cta_goal} />}
            {run.brief.extra_notes && (
              <BriefRow label="Notas" value={run.brief.extra_notes} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function ScriptLine({ label, text }: { label: string; text: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
      <p className="text-sm leading-relaxed text-zinc-200">{text}</p>
    </div>
  );
}

function BriefRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] uppercase tracking-wider text-zinc-500">{label}</span>
      <p className="text-sm text-zinc-200">{value}</p>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "relative -mb-px flex items-center gap-1.5 border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
        active
          ? "border-violet-400 text-zinc-50"
          : "border-transparent text-zinc-500 hover:text-zinc-300"
      )}
    >
      {children}
    </button>
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
