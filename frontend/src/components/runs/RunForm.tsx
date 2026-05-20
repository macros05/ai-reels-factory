import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  CheckCircle2,
  Clapperboard,
  Loader2,
  Pencil,
  Sparkles,
  Wand2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useCharacters } from "@/hooks/useCharacters";
import { useCreateRun } from "@/hooks/useCreateRun";
import { useProviders } from "@/hooks/useProviders";
import { BriefBuilder } from "./BriefBuilder";
import { CharacterSelect } from "./CharacterSelect";
import { ProviderSelect } from "./ProviderSelect";
import { ReferenceUploader } from "./ReferenceUploader";
import { ScriptEditor } from "./ScriptEditor";
import { ApiError, api } from "@/lib/api";
import type { CreativeBrief } from "@/types";

const PLACEHOLDERS = [
  "cómo dormir mejor sin pastillas",
  "tendencias de café especialidad 2026",
  "rutina de 5 minutos para la mañana",
  "el truco de productividad que cambió mi semana",
  "lo que aprendí entrenando 30 días seguidos",
];

const MAX_LENGTH = 4000;

const STEP_LABELS: Record<string, string> = {
  script_generator: "Componiendo guion",
  style_extractor: "Leyendo tus referencias",
  director: "Dirigiendo el shot plan",
  voice_generator: "Sintetizando voz",
  video_generator: "Renderizando clips en Higgsfield",
  subtitle_generator: "Transcribiendo y subtitulando",
  assembler: "Ensamblando el reel final",
};

const STEP_ORDER = [
  "script_generator",
  "style_extractor",
  "director",
  "voice_generator",
  "video_generator",
  "subtitle_generator",
  "assembler",
];

function newDraftRunId(): string {
  const ts = new Date().toISOString().replace(/[-:TZ.]/g, "").slice(0, 14);
  const rand = Math.random().toString(36).slice(2, 8);
  return `${ts.slice(0, 8)}-${ts.slice(8)}-${rand}`;
}

export function RunForm() {
  const create = useCreateRun();
  const { data: providers } = useProviders();
  const { data: charactersResp } = useCharacters();
  const characters = charactersResp?.characters ?? [];
  const navigate = useNavigate();

  const [topic, setTopic] = useState("");
  const [provider, setProvider] = useState<string>("");
  const [soulId, setSoulId] = useState<string | null>(null);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [brief, setBrief] = useState<Partial<CreativeBrief>>({});
  const [voiceless, setVoiceless] = useState(false);
  const [useKeyframes, setUseKeyframes] = useState(false);
  // Default = autonomous (Claude dirige todo). Opt-in para editar a mano.
  const [editScriptManually, setEditScriptManually] = useState(false);

  const [draftRunId, setDraftRunId] = useState<string>(() => newDraftRunId());
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  useEffect(() => {
    const t = setInterval(() => {
      setPlaceholderIdx((i) => (i + 1) % PLACEHOLDERS.length);
    }, 3500);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (providers && !provider) setProvider(providers.current);
  }, [providers, provider]);

  const activeRun = useQuery({
    queryKey: ["run", activeRunId],
    queryFn: () => api.getRun(activeRunId!),
    enabled: !!activeRunId,
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      if (!s) return 2000;
      if (s === "done" || s === "failed") return false;
      return 2000;
    },
  });

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = topic.trim();
    if (!trimmed) return;
    try {
      const briefPayload = isBriefEmpty(brief) ? null : { ...brief, topic: trimmed };
      const res = await create.mutateAsync({
        topic: trimmed,
        provider: provider || undefined,
        draft: editScriptManually,
        runId: draftRunId,
        soulId: soulId ?? undefined,
        brief: briefPayload,
        voiceless,
        useKeyframes,
      });
      setActiveRunId(res.run_id);
      if (editScriptManually) {
        toast.success("Componiendo guion editable…");
      } else {
        toast.success("Claude está dirigiendo tu reel", {
          description: "Guion → director → voz → vídeo → ensamblado, autónomo.",
        });
      }
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Error inesperado";
      toast.error(msg);
    }
  }

  function startOver() {
    setActiveRunId(null);
    setTopic("");
    setSoulId(null);
    setBrief({});
    setVoiceless(false);
    setUseKeyframes(false);
    setEditScriptManually(false);
    setDraftRunId(newDraftRunId());
  }

  const activeProvider = providers?.available.find(
    (p) => p.id === (provider || providers.current)
  );
  const characterUnsupported = activeProvider ? !activeProvider.supports_soul_id : false;
  const status = activeRun.data?.status;
  const currentStep = activeRun.data?.current_step ?? null;
  const finished = status === "done" || status === "failed";

  useEffect(() => {
    if (status === "done" && activeRunId) {
      // Whisk the user to the finished reel detail page so they see the
      // result. Autonomous mode = no need for them to do anything more here.
      const id = activeRunId;
      const t = setTimeout(() => navigate(`/run/${id}`), 400);
      return () => clearTimeout(t);
    }
    if (status === "failed") {
      const t = setTimeout(startOver, 1500);
      return () => clearTimeout(t);
    }
  }, [status, activeRunId, navigate]);

  // ── State A: editor opt-in flow paused at script_ready ──
  if (
    editScriptManually &&
    activeRun.data?.status === "script_ready" &&
    activeRun.data.script
  ) {
    return (
      <div className="flex flex-col gap-3">
        <ScriptEditor runId={activeRun.data.run_id} initial={activeRun.data.script} />
        <button
          type="button"
          onClick={startOver}
          className="self-center text-xs text-zinc-500 underline-offset-2 transition-colors hover:text-zinc-300 hover:underline"
        >
          empezar otro reel
        </button>
      </div>
    );
  }

  // ── State B: autonomous run in progress ──
  if (activeRunId && !finished && !editScriptManually) {
    return (
      <AutonomousProgress
        topic={topic}
        currentStep={currentStep}
        onCancel={startOver}
      />
    );
  }

  // ── State C: form ──
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-6 p-6 sm:p-8">
        <form onSubmit={handleSubmit} className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2 text-xs text-zinc-400">
              <Clapperboard className="size-3.5 text-violet-300" />
              <span className="font-medium uppercase tracking-[0.16em]">
                Brief del reel
              </span>
            </div>
            <div className="relative">
              <Textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value.slice(0, MAX_LENGTH))}
                placeholder={`Ej: ${PLACEHOLDERS[placeholderIdx]}\n\nDescribe qué quieres contar y a quién. Cuanto más rico el contexto, más afinado todo.`}
                rows={8}
                disabled={create.isPending}
                className="min-h-[200px] pr-20 text-[15px] leading-relaxed"
              />
              <span className="mono pointer-events-none absolute bottom-3 right-4 text-[11px] text-zinc-500">
                {topic.length}/{MAX_LENGTH}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500">
              Sólo prompt + referencias. Claude se encarga del guion, el shot
              plan, la voz, el render y el ensamblado.
            </p>
          </div>

          <BriefBuilder
            value={brief}
            onChange={setBrief}
            disabled={create.isPending}
          />

          {providers && (
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
                Proveedor de vídeo
              </label>
              <ProviderSelect
                providers={providers.available}
                value={provider || providers.current}
                defaultValue={providers.current}
                onChange={setProvider}
                disabled={create.isPending}
              />
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium uppercase tracking-[0.16em] text-zinc-400">
              Character (Soul ID) ·{" "}
              <span className="text-[11px] font-normal normal-case tracking-normal text-zinc-500">
                opcional
              </span>
            </label>
            <CharacterSelect
              characters={characters}
              value={soulId}
              onChange={setSoulId}
              disabled={create.isPending}
              unsupported={characterUnsupported}
            />
            <p className="text-[11px] text-zinc-500">
              Si seleccionas un character, cada clip llevará la misma cara como
              start-image — coherencia entre clips garantizada.
            </p>
          </div>

          <ReferenceUploader runId={draftRunId} disabled={create.isPending} />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ToggleRow
              label="Voiceless (sólo música)"
              hint="Sin ElevenLabs — pista de música o audio nativo del proveedor."
              checked={voiceless}
              onChange={setVoiceless}
              disabled={create.isPending}
            />
            <ToggleRow
              label="Keyframes con Nano-Banana-Pro"
              hint="Una imagen por clip como start-image — control extra de composición."
              checked={useKeyframes}
              onChange={setUseKeyframes}
              disabled={create.isPending}
            />
          </div>

          <div className="rounded-xl border border-white/[0.05] bg-white/[0.015] px-3.5 py-3">
            <ToggleRow
              label="Modo experto · editar guion a mano"
              hint="Pausa tras el guion para que lo edites antes del director. Por defecto desactivado — Claude lleva todo."
              checked={editScriptManually}
              onChange={setEditScriptManually}
              disabled={create.isPending}
            />
          </div>

          <Button
            type="submit"
            size="xl"
            disabled={create.isPending || !topic.trim()}
            className="ring-conic w-full"
          >
            {create.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Lanzando…
              </>
            ) : editScriptManually ? (
              <>
                <Pencil className="size-4" />
                Generar guion editable
              </>
            ) : (
              <>
                <Wand2 className="size-4" />
                Crear reel · Claude lo dirige
              </>
            )}
          </Button>
          <p className="text-center text-[11px] text-zinc-500">
            <Sparkles className="mr-1 inline-block size-3 text-violet-300" />
            Flujo autónomo: guion → director frame-by-frame · auto-revisión → voz →
            vídeo → ensamblado
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

function AutonomousProgress({
  topic,
  currentStep,
  onCancel,
}: {
  topic: string;
  currentStep: string | null;
  onCancel: () => void;
}) {
  const activeIdx = currentStep ? STEP_ORDER.indexOf(currentStep) : 0;
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-7 p-6 sm:p-8">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <Sparkles className="size-3.5 animate-pulse text-violet-300" />
            <span className="font-medium uppercase tracking-[0.16em]">
              Claude dirigiendo
            </span>
          </div>
          <h2 className="text-balance text-2xl font-semibold tracking-tight text-zinc-50">
            {topic.length > 80 ? topic.slice(0, 80) + "…" : topic}
          </h2>
        </div>

        <ol className="flex flex-col gap-2.5">
          {STEP_ORDER.map((stepKey, idx) => {
            const isActive = currentStep === stepKey;
            const isPast = activeIdx > idx;
            return (
              <li key={stepKey} className="flex items-center gap-3">
                <div
                  className={`flex size-6 shrink-0 items-center justify-center rounded-full ${
                    isPast
                      ? "bg-violet-500/20 text-violet-200 ring-1 ring-inset ring-violet-400/30"
                      : isActive
                        ? "bg-violet-500 text-white"
                        : "bg-white/[0.04] text-zinc-600 ring-1 ring-inset ring-white/[0.06]"
                  }`}
                >
                  {isPast ? (
                    <CheckCircle2 className="size-3.5" />
                  ) : isActive ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <span className="mono text-[10px]">{idx + 1}</span>
                  )}
                </div>
                <span
                  className={`text-sm transition-colors ${
                    isActive
                      ? "text-zinc-50"
                      : isPast
                        ? "text-zinc-300"
                        : "text-zinc-500"
                  }`}
                >
                  {STEP_LABELS[stepKey] ?? stepKey}
                </span>
              </li>
            );
          })}
        </ol>

        <div className="flex items-center justify-between border-t border-white/[0.05] pt-4">
          <p className="text-[11px] text-zinc-500">
            Puedes cerrar esta pestaña: el run sigue corriendo en el servidor.
          </p>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            <XCircle className="size-3.5" />
            Otro reel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
  disabled,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`group flex items-start justify-between gap-3 rounded-xl border px-3.5 py-3 text-left transition-all ${
        checked
          ? "border-violet-400/40 bg-violet-500/[0.06]"
          : "border-white/[0.06] bg-white/[0.02] hover:border-white/[0.12]"
      } disabled:opacity-50`}
    >
      <div className="flex flex-col gap-0.5">
        <span className="text-xs font-semibold text-zinc-100">{label}</span>
        <span className="text-[11px] leading-relaxed text-zinc-500">{hint}</span>
      </div>
      <span
        className={`relative mt-0.5 inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
          checked ? "bg-violet-500" : "bg-white/[0.08]"
        }`}
      >
        <span
          className={`inline-block size-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </span>
    </button>
  );
}

function isBriefEmpty(b: Partial<CreativeBrief>): boolean {
  return (
    !b.audience?.trim() &&
    !b.palette?.trim() &&
    !b.cta_goal?.trim() &&
    !b.extra_notes?.trim() &&
    !(b.tone?.length) &&
    !(b.mood?.length) &&
    !(b.visual_vibe?.length)
  );
}
