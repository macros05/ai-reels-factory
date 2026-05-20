import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clapperboard, Loader2, Sparkles, Wand2 } from "lucide-react";
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
  const [topic, setTopic] = useState("");
  const [provider, setProvider] = useState<string>("");
  const [soulId, setSoulId] = useState<string | null>(null);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const [brief, setBrief] = useState<Partial<CreativeBrief>>({});
  const [voiceless, setVoiceless] = useState(false);
  const [useKeyframes, setUseKeyframes] = useState(false);

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
        draft: true,
        runId: draftRunId,
        soulId: soulId ?? undefined,
        brief: briefPayload,
        voiceless,
        useKeyframes,
      });
      setActiveRunId(res.run_id);
      toast.success("Componiendo guion…", {
        description:
          "Cuando esté listo lo podrás editar antes de pasar al director, voz y vídeo.",
      });
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
    setDraftRunId(newDraftRunId());
  }

  const activeProvider = providers?.available.find(
    (p) => p.id === (provider || providers.current)
  );
  const characterUnsupported = activeProvider ? !activeProvider.supports_soul_id : false;

  if (activeRun.data?.status === "script_ready" && activeRun.data.script) {
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

  const status = activeRun.data?.status;
  const showWaiting =
    !!activeRunId &&
    (status === "pending" || status === "running") &&
    activeRun.data?.current_step !== null;
  const finished = status === "done" || status === "failed";

  useEffect(() => {
    if (!finished) return;
    const t = setTimeout(startOver, 100);
    return () => clearTimeout(t);
  }, [finished]);

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
                placeholder={`Ej: ${PLACEHOLDERS[placeholderIdx]}\n\nPuedes pegar un brief largo: público, tono, datos concretos, llamadas a la acción…`}
                rows={8}
                disabled={create.isPending || showWaiting}
                className="min-h-[180px] pr-20 text-[15px] leading-relaxed"
              />
              <span className="mono pointer-events-none absolute bottom-3 right-4 text-[11px] text-zinc-500">
                {topic.length}/{MAX_LENGTH}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500">
              Cuanto más contexto, mejor el guion. Hasta 4000 caracteres — afinas debajo
              con tono, mood y vibra visual.
            </p>
          </div>

          <BriefBuilder
            value={brief}
            onChange={setBrief}
            disabled={create.isPending || showWaiting}
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
                disabled={create.isPending || showWaiting}
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
              disabled={create.isPending || showWaiting}
              unsupported={characterUnsupported}
            />
            <p className="text-[11px] text-zinc-500">
              Si seleccionas un character entrenado, cada clip llevará la misma cara
              como start-image — soluciona el "cara distinta en cada clip" de Kling.
            </p>
          </div>

          <ReferenceUploader
            runId={draftRunId}
            disabled={create.isPending || showWaiting}
          />

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <ToggleRow
              label="Voiceless (sólo música)"
              hint="Sin ElevenLabs — pista de música o audio nativo del proveedor."
              checked={voiceless}
              onChange={setVoiceless}
              disabled={create.isPending || showWaiting}
            />
            <ToggleRow
              label="Keyframes con Nano-Banana-Pro"
              hint="Una imagen por clip como start-image — control extra de composición."
              checked={useKeyframes}
              onChange={setUseKeyframes}
              disabled={create.isPending || showWaiting}
            />
          </div>

          <Button
            type="submit"
            size="xl"
            disabled={create.isPending || showWaiting || !topic.trim()}
            className="ring-conic w-full"
          >
            {create.isPending || showWaiting ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                {showWaiting ? "Componiendo guion…" : "Lanzando…"}
              </>
            ) : (
              <>
                <Wand2 className="size-4" />
                Generar guion · editable antes del director
              </>
            )}
          </Button>
          <p className="text-center text-[11px] text-zinc-500">
            <Sparkles className="mr-1 inline-block size-3 text-violet-300" />
            Flujo: guion → director frame-by-frame → voz → vídeo → ensamblado
          </p>
        </form>
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
