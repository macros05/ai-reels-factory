import { useState } from "react";
import {
  Aperture,
  Camera,
  Film,
  Lightbulb,
  Loader2,
  Palette,
  RefreshCw,
  Save,
  Sparkles,
  Wand2,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useReassembleRun,
  useRefineShot,
  useRegenerateClip,
  useUpdateShotPlan,
} from "@/hooks/useCreateRun";
import { ApiError } from "@/lib/api";
import type { Shot, ShotPlan, ShotSize } from "@/types";

const SHOT_SIZES: { value: ShotSize; label: string }[] = [
  { value: "extreme_close_up", label: "ECU" },
  { value: "close_up", label: "CU" },
  { value: "medium_close_up", label: "MCU" },
  { value: "medium", label: "Medium" },
  { value: "medium_wide", label: "MW" },
  { value: "wide", label: "Wide" },
  { value: "extreme_wide", label: "EWS" },
];

/**
 * Frame-by-frame editor of the director's ShotPlan. Two ways to mutate a shot:
 *
 * 1. Hand-edit any field below — saved in bulk with "Guardar plan" via
 *    PUT /api/runs/{id}/shot-plan.
 * 2. Refine the active shot via natural-language instruction → Claude rewrites
 *    just that shot via POST /api/runs/{id}/shot-plan/refine.
 *
 * The active shot is the one being edited; we tab between them with a column
 * of clip cards on the left.
 */
export function ShotPlanEditor({
  runId,
  initial,
  readOnly,
}: {
  runId: string;
  initial: ShotPlan;
  readOnly?: boolean;
}) {
  const [plan, setPlan] = useState<ShotPlan>(initial);
  const [active, setActive] = useState(0);
  const [instruction, setInstruction] = useState("");
  const update = useUpdateShotPlan();
  const refine = useRefineShot();
  const regenerate = useRegenerateClip();
  const reassemble = useReassembleRun();

  const shot = plan.shots[active];

  function patchShot(patch: Partial<Shot>) {
    setPlan((p) => ({
      ...p,
      shots: p.shots.map((s, i) => (i === active ? { ...s, ...patch } : s)),
    }));
  }

  async function handleSave() {
    try {
      await update.mutateAsync({ runId, plan });
      toast.success("Shot plan guardado");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al guardar");
    }
  }

  async function handleRefine() {
    const trimmed = instruction.trim();
    if (!trimmed) return;
    try {
      const res = await refine.mutateAsync({
        runId,
        shotIndex: active,
        instruction: trimmed,
      });
      setPlan((p) => ({
        ...p,
        shots: p.shots.map((s, i) => (i === active ? res.shot : s)),
      }));
      setInstruction("");
      toast.success("Shot refinado por el director");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al refinar");
    }
  }

  async function handleRegenerateClip() {
    try {
      // Persist any pending edits so the backend uses the latest prompt.
      await update.mutateAsync({ runId, plan });
      await regenerate.mutateAsync({ runId, clipIndex: active });
      toast.success(`Clip ${active + 1} regenerado. Re-ensambla cuando estés listo.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al regenerar clip");
    }
  }

  async function handleReassemble() {
    try {
      await reassemble.mutateAsync({ runId });
      toast.success("Vídeo re-ensamblado");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al re-ensamblar");
    }
  }

  if (!shot) {
    return (
      <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 text-sm text-zinc-400">
        Sin shot plan disponible.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Plan header */}
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Film className="size-3.5 text-violet-300" />
            <span className="font-medium uppercase tracking-[0.16em]">Shot plan</span>
          </div>
          {plan.title && (
            <h3 className="mt-1 text-lg font-semibold text-zinc-50">{plan.title}</h3>
          )}
          {plan.logline && (
            <p className="mt-1 max-w-2xl text-sm text-zinc-400">{plan.logline}</p>
          )}
        </div>
        {!readOnly && (
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={handleSave}
              variant="secondary"
              size="sm"
              disabled={update.isPending}
            >
              {update.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Save className="size-3.5" />
              )}
              Guardar plan
            </Button>
            <Button
              onClick={handleReassemble}
              variant="outline"
              size="sm"
              disabled={reassemble.isPending}
            >
              {reassemble.isPending ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : (
                <Wrench className="size-3.5" />
              )}
              Re-ensamblar vídeo
            </Button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-[280px_1fr]">
        {/* Clip rail */}
        <div className="flex flex-row gap-2 overflow-x-auto md:flex-col md:overflow-x-visible">
          {plan.shots.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => setActive(i)}
              className={`group flex min-w-[180px] flex-col gap-1 rounded-xl border px-3 py-2.5 text-left transition-all ${
                i === active
                  ? "border-violet-400/40 bg-violet-500/10"
                  : "border-white/[0.05] bg-white/[0.02] hover:border-white/[0.12] hover:bg-white/[0.04]"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="mono text-[10px] text-zinc-500">CLIP {i + 1}</span>
                <span
                  className={`mono rounded-full px-1.5 py-0.5 text-[9px] uppercase tracking-wider ${
                    i === active
                      ? "bg-violet-500/30 text-violet-100"
                      : "bg-white/[0.04] text-zinc-400"
                  }`}
                >
                  {labelForSize(s.shot_size)}
                </span>
              </div>
              <div className="line-clamp-2 text-xs text-zinc-200">
                {s.dialogue_excerpt || s.location || "—"}
              </div>
              <div className="mono mt-0.5 text-[10px] text-zinc-500">
                {s.lens_mm}mm · {s.duration_seconds}s
              </div>
            </button>
          ))}
        </div>

        {/* Active shot editor */}
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <div>
              <div className="mono text-[10px] uppercase tracking-wider text-zinc-500">
                Shot {active + 1} de {plan.shots.length}
              </div>
              <h4 className="text-base font-semibold text-zinc-50">
                {shot.location || "Sin localización"}
              </h4>
            </div>
            <span className="mono text-[10px] text-zinc-500">
              {shot.duration_seconds}s · {shot.lens_mm}mm · {shot.aperture}
            </span>
          </div>

          {/* Refine via Claude */}
          {!readOnly && (
            <div className="mb-5 rounded-xl border border-violet-400/15 bg-violet-500/[0.06] p-3">
              <div className="mb-2 flex items-center gap-2 text-xs font-medium text-violet-200">
                <Wand2 className="size-3.5" /> Pedir al director
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  placeholder="Ej: amplía a wide al amanecer con la persona vista de espaldas"
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  disabled={refine.isPending}
                  className="flex-1"
                />
                <Button
                  type="button"
                  size="md"
                  onClick={handleRefine}
                  disabled={refine.isPending || !instruction.trim()}
                  className="shrink-0"
                >
                  {refine.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="size-3.5" />
                  )}
                  Refinar
                </Button>
              </div>
              <p className="mt-2 text-[11px] text-zinc-500">
                Claude reescribe sólo este shot y respeta persona_lock + style_brief.
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-violet-400/10 pt-3">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleRegenerateClip}
                  disabled={regenerate.isPending}
                >
                  {regenerate.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="size-3.5" />
                  )}
                  Regenerar este clip
                </Button>
                <span className="text-[11px] text-zinc-500">
                  Sólo re-renderiza el clip actual con el prompt guardado.
                  Recuerda re-ensamblar el vídeo cuando termines.
                </span>
              </div>
            </div>
          )}

          {/* Fields */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="Shot size" icon={Camera}>
              <select
                value={shot.shot_size}
                disabled={readOnly}
                onChange={(e) => patchShot({ shot_size: e.target.value as ShotSize })}
                className="h-10 w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 text-sm text-zinc-100 transition-colors hover:border-white/[0.14] focus:outline-none focus:border-violet-400/50"
              >
                {SHOT_SIZES.map((s) => (
                  <option key={s.value} value={s.value} className="bg-zinc-900">
                    {s.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Lens (mm)" icon={Aperture}>
              <Input
                type="number"
                value={shot.lens_mm}
                disabled={readOnly}
                onChange={(e) => patchShot({ lens_mm: Number(e.target.value) || 0 })}
              />
            </Field>
            <Field label="Aperture">
              <Input
                value={shot.aperture}
                disabled={readOnly}
                onChange={(e) => patchShot({ aperture: e.target.value })}
              />
            </Field>
            <Field label="Camera move">
              <Input
                value={shot.camera_move}
                disabled={readOnly}
                onChange={(e) => patchShot({ camera_move: e.target.value })}
              />
            </Field>
            <Field label="Lighting" icon={Lightbulb}>
              <Input
                value={shot.lighting}
                disabled={readOnly}
                onChange={(e) => patchShot({ lighting: e.target.value })}
              />
            </Field>
            <Field label="Color palette" icon={Palette}>
              <Input
                value={shot.color_palette}
                disabled={readOnly}
                onChange={(e) => patchShot({ color_palette: e.target.value })}
              />
            </Field>
            <Field label="Location">
              <Input
                value={shot.location}
                disabled={readOnly}
                onChange={(e) => patchShot({ location: e.target.value })}
              />
            </Field>
            <Field label="Wardrobe">
              <Input
                value={shot.wardrobe}
                disabled={readOnly}
                onChange={(e) => patchShot({ wardrobe: e.target.value })}
              />
            </Field>
            <Field label="Emotion">
              <Input
                value={shot.emotion}
                disabled={readOnly}
                onChange={(e) => patchShot({ emotion: e.target.value })}
              />
            </Field>
            <Field label="Transitions">
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="in"
                  value={shot.transition_in}
                  disabled={readOnly}
                  onChange={(e) => patchShot({ transition_in: e.target.value })}
                />
                <Input
                  placeholder="out"
                  value={shot.transition_out}
                  disabled={readOnly}
                  onChange={(e) => patchShot({ transition_out: e.target.value })}
                />
              </div>
            </Field>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4">
            <Field label="Dialogue excerpt">
              <Textarea
                rows={2}
                value={shot.dialogue_excerpt}
                disabled={readOnly}
                onChange={(e) => patchShot({ dialogue_excerpt: e.target.value })}
              />
            </Field>
            <Field label="Action beats">
              <Textarea
                rows={3}
                value={shot.action_beats.join("\n")}
                disabled={readOnly}
                onChange={(e) =>
                  patchShot({
                    action_beats: e.target.value
                      .split("\n")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="Un beat por línea — formato [0s-2s] descripción"
              />
            </Field>
            <Field label="Props">
              <Input
                value={shot.props.join(", ")}
                disabled={readOnly}
                onChange={(e) =>
                  patchShot({
                    props: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
                placeholder="Separados por comas"
              />
            </Field>
            <Field
              label="Prompt final (enviado a Higgsfield)"
              hint="Lo que el video provider recibe literalmente"
            >
              <Textarea
                rows={4}
                value={shot.final_prompt}
                disabled={readOnly}
                onChange={(e) => patchShot({ final_prompt: e.target.value })}
                className="mono text-[12.5px] leading-relaxed"
              />
            </Field>
          </div>
        </div>
      </div>

      {/* Persona lock + style brief + camera directive — read-only strips */}
      {(plan.persona_lock || plan.style_brief || plan.camera_directive) && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {plan.camera_directive && (
            <InfoStrip
              label="Camera directive"
              value={plan.camera_directive}
              tone="violet"
            />
          )}
          {plan.persona_lock && (
            <InfoStrip label="Persona lock" value={plan.persona_lock} />
          )}
          {plan.style_brief && (
            <InfoStrip label="Style brief" value={plan.style_brief} />
          )}
        </div>
      )}
    </div>
  );
}

function Field({
  label,
  icon: Icon,
  hint,
  children,
}: {
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-zinc-400">
        {Icon && <Icon className="size-3.5 text-zinc-500" />}
        {label}
      </label>
      {children}
      {hint && <span className="text-[10.5px] text-zinc-500">{hint}</span>}
    </div>
  );
}

function InfoStrip({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "violet";
}) {
  const accent =
    tone === "violet"
      ? "border-violet-400/20 bg-violet-500/[0.06]"
      : "border-white/[0.05] bg-white/[0.02]";
  const labelColor =
    tone === "violet" ? "text-violet-300" : "text-zinc-500";
  return (
    <div className={`rounded-xl border px-4 py-3 ${accent}`}>
      <div className={`mono text-[10px] uppercase tracking-wider ${labelColor}`}>
        {label}
      </div>
      <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-300">{value}</p>
    </div>
  );
}

function labelForSize(s: ShotSize): string {
  return SHOT_SIZES.find((x) => x.value === s)?.label ?? s;
}
