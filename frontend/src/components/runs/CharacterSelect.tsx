import { useState } from "react";
import { ChevronDown, Loader2, User, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Character } from "@/types";

interface Props {
  characters: Character[];
  value: string | null;
  onChange: (soulId: string | null) => void;
  disabled?: boolean;
  /** True when the active provider can't use Soul IDs (e.g. Veo). */
  unsupported?: boolean;
}

/**
 * Compact dropdown for selecting a trained Soul-ID character to lock the
 * face across all clips. Only "ready" characters are selectable; training
 * ones are listed greyed-out so the user can see progress.
 */
export function CharacterSelect({ characters, value, onChange, disabled, unsupported }: Props) {
  const [open, setOpen] = useState(false);
  const selected = characters.find((c) => c.soul_id === value);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => !disabled && !unsupported && setOpen((o) => !o)}
        disabled={disabled || unsupported}
        className={cn(
          "flex w-full items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5 text-left text-sm transition-colors",
          "hover:border-zinc-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/50",
          (disabled || unsupported) && "cursor-not-allowed opacity-60"
        )}
      >
        <div className="flex items-center gap-2 truncate">
          <User className="size-4 shrink-0 text-zinc-500" />
          {selected ? (
            <span className="truncate text-zinc-100">{selected.name}</span>
          ) : (
            <span className="text-zinc-500">
              {unsupported
                ? "El proveedor activo no soporta Soul ID"
                : "Sin character (cara aleatoria por clip)"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {selected && !disabled && (
            <span
              role="button"
              tabIndex={0}
              aria-label="Quitar character"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange(null);
                }
              }}
              className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300 focus:outline-none focus-visible:ring-1 focus-visible:ring-zinc-500"
            >
              <X className="size-3" />
            </span>
          )}
          <ChevronDown className="size-4 text-zinc-500" />
        </div>
      </button>

      {open && (
        <div className="absolute z-10 mt-1 max-h-72 w-full overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-950/95 p-1 shadow-lg shadow-black/40 backdrop-blur">
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setOpen(false);
            }}
            className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm text-zinc-300 hover:bg-zinc-800/60"
          >
            <X className="size-3 text-zinc-500" />
            <span className="text-zinc-400">Sin character</span>
          </button>
          {characters.length === 0 && (
            <p className="px-2 py-3 text-center text-xs text-zinc-500">
              Aún no has entrenado ninguno.{" "}
              <span className="text-zinc-400">Crea uno en la pestaña "Characters"</span>.
            </p>
          )}
          {characters.map((c) => {
            const ready = c.status === "ready";
            return (
              <button
                key={c.soul_id}
                type="button"
                disabled={!ready}
                onClick={() => {
                  if (!ready) return;
                  onChange(c.soul_id);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors",
                  ready
                    ? "text-zinc-100 hover:bg-zinc-800/60"
                    : "cursor-not-allowed text-zinc-500"
                )}
              >
                <div className="flex items-center gap-2 truncate">
                  <User className="size-4 shrink-0 text-zinc-500" />
                  <span className="truncate">{c.name}</span>
                </div>
                {c.status === "training" ? (
                  <span className="inline-flex items-center gap-1 rounded-md border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
                    <Loader2 className="size-3 animate-spin" />
                    training
                  </span>
                ) : c.status === "failed" ? (
                  <span className="rounded-md border border-rose-500/30 bg-rose-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-rose-300">
                    failed
                  </span>
                ) : (
                  <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-300">
                    ready
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
