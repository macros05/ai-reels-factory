import { useRef, useState } from "react";
import {
  ImageIcon,
  Mic,
  Music,
  Palette,
  Sparkles,
  Upload,
  Youtube,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  useReferences,
  useUploadReference,
  useYoutubeReference,
} from "@/hooks/useReferences";
import type { Reference, ReferenceKind } from "@/types";
import { ApiError } from "@/lib/api";

type FileTab = {
  kind: ReferenceKind;
  label: string;
  icon: typeof ImageIcon;
  accept: string;
  hint: string;
};

const FILE_TABS: FileTab[] = [
  {
    kind: "persona",
    label: "Persona",
    icon: ImageIcon,
    accept: "image/jpeg,image/png,image/webp",
    hint: "Foto del protagonista (1:1 o vertical, ≥512px). Sube varias si quieres.",
  },
  {
    kind: "style",
    label: "Estilo",
    icon: Palette,
    accept: "image/jpeg,image/png,image/webp,video/mp4,video/quicktime",
    hint: "Imagen o vídeo corto que defina la estética (color, luz, encuadre).",
  },
];

type YtKind = "script" | "voice" | "music";

type YtSection = {
  kind: YtKind;
  label: string;
  icon: typeof Sparkles;
  accept: string;
  fileHint: string;
  ytPlaceholder: string;
  bgGlow: string;
};

const YT_SECTIONS: YtSection[] = [
  {
    kind: "script",
    label: "Guion",
    icon: Sparkles,
    accept: "text/plain",
    fileHint: "Sube un .txt con el transcript. Solo inspira ángulo y estructura, no se copia.",
    ytPlaceholder:
      "https://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=...\n(uno por línea)",
    bgGlow: "from-violet-500/10",
  },
  {
    kind: "voice",
    label: "Voz",
    icon: Mic,
    accept: "audio/mpeg,audio/wav,audio/mp4,audio/aac",
    fileHint:
      "Audio (≥30 s) con la voz a clonar. La voz clonada se borra al terminar el run.",
    ytPlaceholder:
      "https://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=...\n(uno por línea)",
    bgGlow: "from-cyan-500/10",
  },
  {
    kind: "music",
    label: "Música",
    icon: Music,
    accept: "audio/mpeg,audio/wav,audio/mp4,audio/aac,audio/flac",
    fileHint: "Pista de banda sonora. La recortamos a la duración del reel.",
    ytPlaceholder:
      "https://youtube.com/watch?v=...\nhttps://youtube.com/watch?v=...\n(uno por línea)",
    bgGlow: "from-emerald-500/10",
  },
];

export function ReferenceUploader({ runId, disabled }: { runId: string; disabled?: boolean }) {
  const refs = useReferences(runId);
  const list = refs.data?.references ?? [];

  return (
    <div className="flex flex-col gap-5 rounded-2xl border border-white/[0.06] bg-white/[0.02] p-5">
      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-zinc-200">
          Referencias (opcionales)
        </label>
        <p className="text-[11.5px] leading-relaxed text-zinc-500">
          Sube fotos, vídeos, audio o pega URLs de YouTube. La app las usa para
          clavar persona, estética, guion y voz. <strong className="text-zinc-300">Guion · Voz · Música</strong>{" "}
          aceptan varios links de YouTube — uno por línea.
        </p>
      </div>

      {/* Persona + Estilo — small tabbed file-only section */}
      <PersonaStyleSection runId={runId} disabled={disabled} list={list} />

      {/* Guion · Voz · Música — three dedicated sections, each with multi-URL support */}
      <div className="flex flex-col gap-4">
        {YT_SECTIONS.map((s) => (
          <YtRefSection
            key={s.kind}
            section={s}
            runId={runId}
            disabled={disabled}
            list={list.filter((r) => r.kind === s.kind)}
          />
        ))}
      </div>
    </div>
  );
}

/* -------------------- Persona + Estilo -------------------- */

function PersonaStyleSection({
  runId,
  disabled,
  list,
}: {
  runId: string;
  disabled?: boolean;
  list: Reference[];
}) {
  const [tab, setTab] = useState<ReferenceKind>("persona");
  const tabDef = FILE_TABS.find((t) => t.kind === tab)!;
  const upload = useUploadReference();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const items = list.filter((r) => r.kind === "persona" || r.kind === "style");

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const arr = Array.from(files);
    let ok = 0;
    for (const file of arr) {
      try {
        await upload.mutateAsync({ runId, kind: tab, file });
        ok++;
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : `Error al subir ${file.name}`
        );
      }
    }
    if (ok > 0) toast.success(`${ok} ${ok === 1 ? "referencia añadida" : "referencias añadidas"} (${tab})`);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  return (
    <div className="rounded-xl border border-white/[0.05] bg-zinc-950/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="text-[12px] font-medium uppercase tracking-wider text-zinc-300">
          Persona y estilo
        </span>
        <span className="mono text-[10px] text-zinc-600">solo archivos</span>
      </div>
      <div className="mb-3 flex flex-wrap gap-1 rounded-lg bg-zinc-900/60 p-1">
        {FILE_TABS.map((t) => {
          const Icon = t.icon;
          const active = t.kind === tab;
          const count = list.filter((r) => r.kind === t.kind).length;
          return (
            <button
              key={t.kind}
              type="button"
              onClick={() => setTab(t.kind)}
              disabled={disabled}
              className={`flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                active
                  ? "bg-zinc-800/80 text-zinc-50"
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
      <p className="mb-3 text-[11px] text-zinc-500">{tabDef.hint}</p>
      <input
        ref={fileInputRef}
        type="file"
        accept={tabDef.accept}
        multiple
        onChange={(e) => handleFiles(e.target.files)}
        disabled={disabled || upload.isPending}
        className="hidden"
        id={`upload-${tab}`}
      />
      <label
        htmlFor={`upload-${tab}`}
        className={`flex w-full cursor-pointer items-center justify-center gap-2 rounded-md border border-zinc-700 bg-zinc-900/70 px-3 py-2 text-sm text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 ${
          disabled || upload.isPending ? "pointer-events-none opacity-50" : ""
        }`}
      >
        <Upload className="size-3.5" />
        {upload.isPending ? "Subiendo…" : `Subir archivo${tab === "persona" ? "s (puedes seleccionar varios)" : ""}`}
      </label>

      {items.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1">
          {items.map((r, i) => (
            <ReferenceRow key={`${r.kind}-${i}`} item={r} />
          ))}
        </ul>
      )}
    </div>
  );
}

/* -------------------- Guion / Voz / Música (one per kind) -------------------- */

function YtRefSection({
  section,
  runId,
  disabled,
  list,
}: {
  section: YtSection;
  runId: string;
  disabled?: boolean;
  list: Reference[];
}) {
  const upload = useUploadReference();
  const youtube = useYoutubeReference();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [ytBatch, setYtBatch] = useState("");

  async function handleFile(file: File | null) {
    if (!file) return;
    try {
      await upload.mutateAsync({ runId, kind: section.kind, file });
      toast.success(`Referencia añadida (${section.label})`);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Error al subir referencia");
    }
  }

  async function handleYtBatch() {
    const urls = ytBatch
      .split(/[\n,;\s]+/)
      .map((u) => u.trim())
      .filter((u) => u.length > 0);
    if (urls.length === 0) return;
    let ok = 0;
    let fail = 0;
    for (const url of urls) {
      try {
        await youtube.mutateAsync({ runId, kind: section.kind, url });
        ok++;
      } catch (err) {
        fail++;
        toast.error(
          err instanceof ApiError ? err.message : `No se pudo procesar ${url}`
        );
      }
    }
    if (ok > 0) {
      toast.success(
        `${ok} ${ok === 1 ? "URL añadida" : "URLs añadidas"} a ${section.label}` +
          (fail > 0 ? ` · ${fail} fallaron` : "")
      );
      setYtBatch("");
    }
  }

  const Icon = section.icon;
  const lineCount = ytBatch
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0).length;

  return (
    <div
      className={`relative overflow-hidden rounded-xl border border-white/[0.05] bg-zinc-950/40 p-4`}
    >
      {/* subtle glow accent specific to each kind */}
      <div
        className={`pointer-events-none absolute -top-12 right-0 size-44 rounded-full bg-gradient-to-br ${section.bgGlow} to-transparent blur-3xl`}
      />
      <div className="relative flex flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <span className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-wider text-zinc-200">
            <Icon className="size-3.5 text-zinc-400" />
            {section.label}
          </span>
          {list.length > 0 && (
            <span className="mono rounded-full bg-emerald-700/30 px-2 py-0.5 text-[10px] text-emerald-300">
              {list.length} ref{list.length === 1 ? "" : "s"}
            </span>
          )}
        </div>

        {/* File row */}
        <div className="flex flex-col gap-1.5">
          <p className="text-[11px] text-zinc-500">{section.fileHint}</p>
          <input
            ref={fileInputRef}
            type="file"
            accept={section.accept}
            onChange={(e) => handleFile(e.target.files?.[0] ?? null)}
            disabled={disabled || upload.isPending}
            className="hidden"
            id={`upload-${section.kind}`}
          />
          <label
            htmlFor={`upload-${section.kind}`}
            className={`flex w-full cursor-pointer items-center justify-center gap-2 rounded-md border border-zinc-800 bg-zinc-900/60 px-3 py-2 text-[13px] text-zinc-300 transition hover:border-zinc-500 hover:text-zinc-100 ${
              disabled || upload.isPending ? "pointer-events-none opacity-50" : ""
            }`}
          >
            <Upload className="size-3.5" />
            Subir archivo
          </label>
        </div>

        {/* YouTube batch row */}
        <div className="flex flex-col gap-1.5">
          <p className="text-[11px] text-zinc-500">
            Pega varias URLs de YouTube — una por línea. Se descargan y se
            añaden todas a este apartado.
          </p>
          <Textarea
            placeholder={section.ytPlaceholder}
            value={ytBatch}
            onChange={(e) => setYtBatch(e.target.value)}
            disabled={disabled || youtube.isPending}
            rows={3}
            className="mono text-[12.5px]"
          />
          <div className="flex items-center justify-between gap-2">
            <span className="mono text-[10px] text-zinc-500">
              {lineCount > 0
                ? `${lineCount} URL${lineCount === 1 ? "" : "s"} en cola`
                : "sin URLs"}
            </span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleYtBatch}
              disabled={disabled || youtube.isPending || lineCount === 0}
            >
              <Youtube className="size-3.5" />
              {youtube.isPending
                ? "Procesando…"
                : `Añadir ${lineCount > 1 ? `${lineCount} links` : "link"}`}
            </Button>
          </div>
        </div>

        {list.length > 0 && (
          <ul className="mt-1 flex flex-col gap-1">
            {list.map((r, i) => (
              <ReferenceRow key={`${section.kind}-${i}`} item={r} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

/* -------------------- shared row -------------------- */

function ReferenceRow({ item }: { item: Reference }) {
  let name: string;
  if (item.source_url) {
    try {
      const u = new URL(item.source_url);
      name = u.host + u.pathname.slice(0, 32);
    } catch {
      name = item.source_url.slice(0, 40);
    }
  } else {
    name = item.path.split("/").pop() ?? item.path;
  }
  return (
    <li className="flex items-center justify-between gap-2 rounded border border-zinc-800/70 bg-zinc-900/40 px-2.5 py-1.5 text-xs text-zinc-300">
      <span className="mono truncate">
        {item.source_url && (
          <Youtube className="mr-1.5 inline size-3 text-red-400" />
        )}
        {name}
      </span>
      <span className="mono shrink-0 text-[10px] text-zinc-500">
        {(item.bytes / 1024).toFixed(0)} KB
      </span>
    </li>
  );
}
