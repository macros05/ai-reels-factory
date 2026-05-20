import { useEffect, useState } from "react";
import { Loader2, Play, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useConfirmRun } from "@/hooks/useCreateRun";
import type { ScriptOutput } from "@/types";
import { ApiError } from "@/lib/api";

export function ScriptEditor({
  runId,
  initial,
}: {
  runId: string;
  initial: ScriptOutput;
}) {
  const confirm = useConfirmRun();
  const [script, setScript] = useState<ScriptOutput>(initial);

  // Sync editor when the upstream draft re-fetches (e.g. after polling).
  useEffect(() => setScript(initial), [initial]);

  const update = <K extends keyof ScriptOutput>(k: K, v: ScriptOutput[K]) =>
    setScript((s) => ({ ...s, [k]: v }));

  function updateVisualPrompt(idx: number, text: string) {
    setScript((s) => ({
      ...s,
      visual_prompts: s.visual_prompts.map((p, i) => (i === idx ? text : p)),
    }));
  }

  function removeHashtag(idx: number) {
    setScript((s) => ({
      ...s,
      hashtags: s.hashtags.filter((_, i) => i !== idx),
    }));
  }

  function addHashtag(tag: string) {
    const clean = tag.trim().replace(/^#/, "");
    if (!clean) return;
    setScript((s) => ({ ...s, hashtags: [...s.hashtags, clean] }));
  }

  async function handleConfirm() {
    const fullScript = [script.hook, script.body, script.cta]
      .map((s) => s.trim())
      .filter(Boolean)
      .join(" ");
    try {
      await confirm.mutateAsync({
        runId,
        script: { ...script, full_script: fullScript },
      });
      toast.success("Pipeline reanudado — generando voz, vídeo y ensamblado");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al confirmar");
    }
  }

  return (
    <Card className="border-zinc-800">
      <CardContent className="flex flex-col gap-5 p-5 sm:p-6">
        <div className="flex flex-col gap-1">
          <h2 className="text-base font-semibold text-zinc-100">Edita el guion</h2>
          <p className="text-[11px] text-zinc-500">
            Claude generó este borrador. Ajusta lo que quieras y dale a <strong>Generar reel</strong> para
            que arranquen voz, vídeo y ensamblado.
          </p>
        </div>

        <EditableField label="Hook (≤12 palabras)" value={script.hook} onChange={(v) => update("hook", v)} rows={2} />
        <EditableField label="Body" value={script.body} onChange={(v) => update("body", v)} rows={5} />
        <EditableField label="CTA" value={script.cta} onChange={(v) => update("cta", v)} rows={2} />
        <EditableField label="Caption (Instagram)" value={script.caption} onChange={(v) => update("caption", v)} rows={3} />

        <HashtagsEditor
          tags={script.hashtags}
          onRemove={removeHashtag}
          onAdd={addHashtag}
        />

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-zinc-300">
            Prompts visuales por clip
          </label>
          <p className="text-[11px] text-zinc-500">
            Uno por cada clip del reel. Cada prompt empieza por la descripción de la persona y añade acción + cámara.
          </p>
          <div className="flex flex-col gap-2">
            {script.visual_prompts.map((p, i) => (
              <div key={i} className="flex flex-col gap-1">
                <span className="mono text-[10px] text-zinc-500">clip {i.toString().padStart(2, "0")}</span>
                <Textarea
                  rows={3}
                  value={p}
                  onChange={(e) => updateVisualPrompt(i, e.target.value)}
                  className="text-xs"
                />
              </div>
            ))}
          </div>
        </div>

        <EditableField
          label="Persona description"
          value={script.persona_description}
          onChange={(v) => update("persona_description", v)}
          rows={4}
        />

        <Button onClick={handleConfirm} disabled={confirm.isPending} size="lg" className="w-full">
          {confirm.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Confirmando…
            </>
          ) : (
            <>
              <Play className="size-4" /> Generar reel
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

function EditableField({
  label,
  value,
  onChange,
  rows,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  rows: number;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-zinc-300">{label}</label>
      <Textarea rows={rows} value={value} onChange={(e) => onChange(e.target.value)} className="leading-relaxed" />
    </div>
  );
}

function HashtagsEditor({
  tags,
  onRemove,
  onAdd,
}: {
  tags: string[];
  onRemove: (i: number) => void;
  onAdd: (tag: string) => void;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-zinc-300">Hashtags</label>
      <div className="flex flex-wrap gap-1.5">
        {tags.map((t, i) => (
          <span
            key={i}
            className="mono inline-flex items-center gap-1 rounded-full bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-200"
          >
            #{t}
            <button
              type="button"
              onClick={() => onRemove(i)}
              className="text-zinc-500 hover:text-red-400"
              aria-label={`quitar #${t}`}
            >
              <Trash2 className="size-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <Input
          placeholder="añadir hashtag (sin #)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onAdd(draft);
              setDraft("");
            }
          }}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            onAdd(draft);
            setDraft("");
          }}
          disabled={!draft.trim()}
        >
          Añadir
        </Button>
      </div>
    </div>
  );
}
