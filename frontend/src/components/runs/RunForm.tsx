import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useCharacters } from "@/hooks/useCharacters";
import { useCreateRun } from "@/hooks/useCreateRun";
import { useProviders } from "@/hooks/useProviders";
import { CharacterSelect } from "./CharacterSelect";
import { ProviderSelect } from "./ProviderSelect";
import { ReferenceUploader } from "./ReferenceUploader";
import { ScriptEditor } from "./ScriptEditor";
import { ApiError, api } from "@/lib/api";

const PLACEHOLDERS = [
  "cómo dormir mejor sin pastillas",
  "tendencias de café especialidad 2026",
  "rutina de 5 minutos para la mañana",
  "el truco de productividad que cambió mi semana",
  "lo que aprendí entrenando 30 días seguidos",
];

const MAX_LENGTH = 4000;

function newDraftRunId(): string {
  // YYYYMMDD-HHMMSS-xxxxxx matches the server's _SAFE_RUN_ID_RE format.
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

  // Each render holds a candidate run_id that the uploader uses to attach
  // references. The id only "promotes" to a real run when the user submits.
  const [draftRunId, setDraftRunId] = useState<string>(() => newDraftRunId());
  // After submit we track the active run so we can show the editor when its
  // status flips to script_ready.
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

  // Poll the active run while it's pending/running, until we hit script_ready
  // (so we can show the editor) or a terminal state.
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
      // Always use the draft flow so the editor can show up. The pipeline
      // pauses after script_generator and we resume via /confirm.
      const res = await create.mutateAsync({
        topic: trimmed,
        provider: provider || undefined,
        draft: true,
        runId: draftRunId,
        soulId: soulId ?? undefined,
      });
      setActiveRunId(res.run_id);
      toast.success("Generando guion…", {
        description: "Cuando esté listo podrás editarlo antes de la generación de voz y vídeo.",
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
    setDraftRunId(newDraftRunId());
  }

  // Veo3.1 doesn't honour Soul IDs (no per-clip soul-driven still), so we
  // hide the picker when the active provider doesn't support it.
  const activeProvider = providers?.available.find(
    (p) => p.id === (provider || providers.current)
  );
  const characterUnsupported = activeProvider ? !activeProvider.supports_soul_id : false;

  // Show the editor as soon as we have a script_ready run.
  if (activeRun.data?.status === "script_ready" && activeRun.data.script) {
    return (
      <div className="flex flex-col gap-3">
        <ScriptEditor runId={activeRun.data.run_id} initial={activeRun.data.script} />
        <button
          type="button"
          onClick={startOver}
          className="self-center text-xs text-zinc-500 underline-offset-2 hover:text-zinc-300 hover:underline"
        >
          empezar otro reel
        </button>
      </div>
    );
  }

  // Once the run is past script_ready (running voice/video, or done/failed),
  // collapse back to the form so the user can launch another reel.
  const status = activeRun.data?.status;
  const showWaiting =
    !!activeRunId &&
    (status === "pending" || status === "running") &&
    activeRun.data?.current_step !== null;
  const finished = status === "done" || status === "failed";

  // Auto-reset to a fresh form once the run reaches a terminal state.
  // Effect (not inline setState) so we don't trigger a render-phase update.
  useEffect(() => {
    if (!finished) return;
    const t = setTimeout(startOver, 100);
    return () => clearTimeout(t);
  }, [finished]);

  return (
    <Card className="border-zinc-800">
      <CardContent className="flex flex-col gap-5 p-5 sm:p-6">
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium text-zinc-300">Tema o brief del reel</label>
            <div className="relative">
              <Textarea
                value={topic}
                onChange={(e) => setTopic(e.target.value.slice(0, MAX_LENGTH))}
                placeholder={`Ej: ${PLACEHOLDERS[placeholderIdx]}\n\nPuedes pegar un brief largo: público objetivo, tono, datos concretos, llamadas a la acción…`}
                rows={8}
                disabled={create.isPending || showWaiting}
                className="min-h-[160px] pr-16 leading-relaxed"
              />
              <span className="mono pointer-events-none absolute bottom-2 right-3 text-[11px] text-zinc-500">
                {topic.length}/{MAX_LENGTH}
              </span>
            </div>
            <p className="text-[11px] text-zinc-500">
              Cuanto más contexto le des (público, tono, datos), mejor el guion. Hasta 4000 caracteres.
            </p>
          </div>

          {providers && (
            <div className="flex flex-col gap-2">
              <label className="text-sm font-medium text-zinc-300">Proveedor de vídeo</label>
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
            <label className="text-sm font-medium text-zinc-300">
              Character (Soul ID){" "}
              <span className="text-xs font-normal text-zinc-500">— opcional</span>
            </label>
            <CharacterSelect
              characters={characters}
              value={soulId}
              onChange={setSoulId}
              disabled={create.isPending || showWaiting}
              unsupported={characterUnsupported}
            />
            <p className="text-[11px] text-zinc-500">
              Si seleccionas un character entrenado, el video step generará una imagen
              por clip con la misma cara y la usará como start-image. Soluciona el
              "cara distinta en cada clip" de Kling.
            </p>
          </div>

          <ReferenceUploader
            runId={draftRunId}
            disabled={create.isPending || showWaiting}
          />

          <Button
            type="submit"
            size="lg"
            disabled={create.isPending || showWaiting || !topic.trim()}
            className="w-full"
          >
            {create.isPending || showWaiting ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                {showWaiting ? "Generando guion…" : "Lanzando…"}
              </>
            ) : (
              <>
                <Sparkles className="size-4" />
                Generar guion (editable)
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
