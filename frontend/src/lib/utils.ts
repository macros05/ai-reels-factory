import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCost(usd: number | null | undefined): string {
  if (usd == null) return "—";
  return `$${usd.toFixed(2)}`;
}

export function formatCredits(credits: number | null | undefined): string {
  if (credits == null) return "—";
  if (credits >= 1000) return `${(credits / 1000).toFixed(1)}k cr`;
  return `${credits} cr`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return "—";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("es-ES", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "hace un momento";
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  return `hace ${Math.floor(diff / 86400)} d`;
}

const STEP_LABELS: Record<string, string> = {
  script_generator: "Generando guion…",
  voice_generator: "Sintetizando voz…",
  video_generator: "Generando clips de vídeo…",
  subtitle_generator: "Transcribiendo subtítulos…",
  assembler: "Ensamblando reel final…",
};

export function stepLabel(step: string | null | undefined): string {
  if (!step) return "Preparando…";
  return STEP_LABELS[step] ?? step;
}
