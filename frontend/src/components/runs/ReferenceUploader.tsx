import { useRef, useState } from "react";
import { ImageIcon, Mic, Music, Palette, Sparkles, Upload, Youtube } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useReferences, useUploadReference, useYoutubeReference } from "@/hooks/useReferences";
import type { Reference, ReferenceKind } from "@/types";
import { ApiError } from "@/lib/api";

const TABS: { kind: ReferenceKind; label: string; icon: typeof ImageIcon; accept: string; allowYouTube: boolean; hint: string }[] = [
  {
    kind: "persona",
    label: "Persona",
    icon: ImageIcon,
    accept: "image/jpeg,image/png,image/webp",
    allowYouTube: false,
    hint: "Foto de la persona que protagonizará el reel (1:1 o vertical, ≥512px).",
  },
  {
    kind: "style",
    label: "Estilo",
    icon: Palette,
    accept: "image/jpeg,image/png,image/webp,video/mp4,video/quicktime",
    allowYouTube: false,
    hint: "Imagen o vídeo corto que defina la estética (color, luz, encuadre).",
  },
  {
    kind: "script",
    label: "Guion",
    icon: Sparkles,
    accept: "text/plain",
    allowYouTube: true,
    hint: "URL de YouTube o .txt con el transcript de referencia. Solo inspira ángulo y estructura, no se copia.",
  },
  {
    kind: "voice",
    label: "Voz",
    icon: Mic,
    accept: "audio/mpeg,audio/wav,audio/mp4,audio/aac",
    allowYouTube: true,
    hint: "Audio (≥30 s) o URL de YouTube con la voz a clonar. La voz clonada se borra al terminar el run.",
  },
  {
    kind: "music",
    label: "Música",
    icon: Music,
    accept: "audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/flac",
    allowYouTube: true,
    hint: "Pista que sonará bajo la voz como banda sonora (cinematic mood). Sube un mp3 o pega un link de YouTube; lo recortamos a la duración del reel.",
  },
];

export function ReferenceUploader({ runId, disabled }: { runId: string; disabled?: boolean }) {
  const [tab, setTab] = useState<ReferenceKind>("persona");
  const tabDef = TABS.find((t) => t.kind === tab)!;
  const refs = useReferences(runId);
  const upload = useUploadReference();
  const youtube = useYoutubeReference();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ytUrl, setYtUrl] = useState("");

  const list = refs.data?.references ?? [];

  async function handleFile(file: File | null) {
    if (!file) return;
    try {
      await upload.mutateAsync({ runId, kind: tab, file });
      toast.success(`Referencia añadida (${tab})`);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al subir referencia");
    }
  }

  async function handleYouTube() {
    const url = ytUrl.trim();
    if (!url) return;
    try {
      await youtube.mutateAsync({ runId, kind: tab as "script" | "voice" | "music", url });
      toast.success(`Referencia añadida desde YouTube (${tab})`);
      setYtUrl("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al procesar YouTube");
    }
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border border-zinc-800 bg-zinc-950/50 p-4">
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-zinc-300">Referencias (opcionales)</label>
        <p className="text-[11px] text-zinc-500">
          Sube fotos, vídeos, audio o pega URLs de YouTube. La app las usa para clavar persona, estilo, guion y voz.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 rounded-md bg-zinc-900 p-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = t.kind === tab;
          const count = list.filter((r) => r.kind === t.kind).length;
          return (
            <button
              key={t.kind}
              type="button"
              onClick={() => setTab(t.kind)}
              disabled={disabled}
              className={`flex flex-1 items-center justify-center gap-2 rounded px-3 py-2 text-xs font-medium transition ${
                active
                  ? "bg-zinc-800 text-zinc-50"
                  : "text-zinc-400 hover:text-zinc-200"
              }`}
            >
              <Icon className="size-3.5" />
              {t.label}
              {count > 0 && (
                <span className="mono rounded-full bg-emerald-700/40 px-1.5 text-[10px] text-emerald-300">
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <p className="text-[11px] text-zinc-500">{tabDef.hint}</p>

      <div className="flex flex-col gap-2 sm:flex-row">
        <div className="flex flex-1 gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept={tabDef.accept}
            onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
            disabled={disabled || upload.isPending}
            className="hidden"
            id={`upload-${tab}`}
          />
          <label
            htmlFor={`upload-${tab}`}
            className={`flex w-full cursor-pointer items-center justify-center gap-2 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 ${
              disabled || upload.isPending ? "pointer-events-none opacity-50" : ""
            }`}
          >
            <Upload className="size-3.5" />
            Subir archivo
          </label>
        </div>

        {tabDef.allowYouTube && (
          <div className="flex flex-1 gap-2">
            <Input
              placeholder="https://youtube.com/watch?v=…"
              value={ytUrl}
              onChange={(e) => setYtUrl(e.target.value)}
              disabled={disabled || youtube.isPending}
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleYouTube}
              disabled={disabled || youtube.isPending || !ytUrl.trim()}
              className="shrink-0"
            >
              <Youtube className="size-3.5" />
              YT
            </Button>
          </div>
        )}
      </div>

      {list.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {list.map((r, i) => (
            <ReferenceRow key={`${r.kind}-${i}`} ref={r} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ReferenceRow({ ref: r }: { ref: Reference }) {
  const name = r.source_url
    ? new URL(r.source_url).host + new URL(r.source_url).pathname.slice(0, 24)
    : r.path.split("/").pop();
  return (
    <li className="flex items-center justify-between gap-2 rounded border border-zinc-800 bg-zinc-900/50 px-2.5 py-1.5 text-xs text-zinc-300">
      <span className="mono truncate">
        <span className="mr-2 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">{r.kind}</span>
        {name}
      </span>
      <span className="mono text-[10px] text-zinc-500">{(r.bytes / 1024).toFixed(0)} KB</span>
    </li>
  );
}
