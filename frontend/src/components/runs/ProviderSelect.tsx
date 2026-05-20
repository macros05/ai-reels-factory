import { Check, Mic, MicOff } from "lucide-react";
import { motion } from "framer-motion";
import { cn, formatCredits } from "@/lib/utils";
import type { ProviderInfo } from "@/types";

const TIER_STYLES: Record<ProviderInfo["tier"], string> = {
  Económico: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  Equilibrado: "border-violet-500/30 bg-violet-500/10 text-violet-300",
  Premium: "border-amber-500/30 bg-amber-500/10 text-amber-300",
};

interface Props {
  providers: ProviderInfo[];
  value: string;
  defaultValue?: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

export function ProviderSelect({ providers, value, defaultValue, onChange, disabled }: Props) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {providers.map((p) => {
        const selected = p.id === value;
        const isDefault = defaultValue && p.id === defaultValue;
        return (
          <motion.button
            key={p.id}
            type="button"
            onClick={() => !disabled && onChange(p.id)}
            disabled={disabled}
            initial={false}
            animate={{
              borderColor: selected ? "rgb(139 92 246 / 0.6)" : "rgb(39 39 42)",
              backgroundColor: selected ? "rgb(24 24 27 / 0.7)" : "rgb(24 24 27 / 0.4)",
            }}
            className={cn(
              "relative flex flex-col gap-1.5 rounded-lg border p-3.5 text-left transition-shadow",
              "hover:border-zinc-700 hover:shadow-md hover:shadow-black/30",
              "focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50",
              disabled && "cursor-not-allowed opacity-60"
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-zinc-100">{p.name}</span>
              {selected && (
                <div className="flex size-4 items-center justify-center rounded-full bg-violet-500 text-white">
                  <Check className="size-3" strokeWidth={3} />
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <span
                className={cn(
                  "w-fit rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                  TIER_STYLES[p.tier]
                )}
              >
                {p.tier}
              </span>
              <span
                className={cn(
                  "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
                  p.native_audio
                    ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                    : "border-zinc-700 bg-zinc-800/60 text-zinc-400"
                )}
                title={
                  p.native_audio
                    ? "Audio nativo del modelo (sin ElevenLabs)"
                    : "Voz vía ElevenLabs + lip-sync inline"
                }
              >
                {p.native_audio ? <MicOff className="size-3" /> : <Mic className="size-3" />}
                {p.native_audio ? "Audio nativo" : "ElevenLabs"}
              </span>
              {p.supports_soul_id && (
                <span className="rounded-md border border-fuchsia-500/30 bg-fuchsia-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-fuchsia-300">
                  Soul ID
                </span>
              )}
              {isDefault && (
                <span className="rounded-md border border-zinc-700 bg-zinc-800/60 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-400">
                  Por defecto
                </span>
              )}
            </div>
            <div className="mt-1 flex items-baseline justify-between">
              <span className="mono text-[11px] text-zinc-500">
                {p.clips}×{p.clip_duration}s · {p.total_duration}s
              </span>
              <span className="mono text-xs font-medium text-zinc-200">
                {formatCredits(p.cost_credits)}
              </span>
            </div>
          </motion.button>
        );
      })}
      <p className="col-span-full text-[11px] text-zinc-500">
        Elige el proveedor para este reel. <span className="text-zinc-400">Veo</span> usa audio
        nativo (no toca ElevenLabs); <span className="text-zinc-400">Kling/Seedance</span> usan tu
        voz clonada en ElevenLabs y la inyectan como lip-sync. Por defecto:{" "}
        <code className="mono rounded bg-zinc-800/60 px-1 py-0.5 text-[10px]">VIDEO_PROVIDER</code>{" "}
        del servidor.
      </p>
    </div>
  );
}
