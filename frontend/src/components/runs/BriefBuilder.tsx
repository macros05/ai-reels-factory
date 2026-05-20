import { ChevronDown, Sliders } from "lucide-react";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { CreativeBrief } from "@/types";

/**
 * Optional structured creative brief. The user can keep it collapsed — a bare
 * topic still works — but expanding it unlocks the chips that nudge the script
 * and the director toward a specific tonal & visual register.
 *
 * We treat tone/mood/visual_vibe as multi-select tag clouds with a default
 * vocabulary; users can free-type to add their own. Everything maps 1:1 to
 * the `CreativeBrief` pydantic model on the backend.
 */

const TONE_PRESETS = [
  "directo",
  "íntimo",
  "energético",
  "calmado",
  "irónico",
  "inspirador",
  "técnico",
  "didáctico",
  "vulnerable",
];

const MOOD_PRESETS = [
  "cinematográfico",
  "documental",
  "minimalista",
  "soñador",
  "urgente",
  "nostálgico",
  "premium",
  "underground",
];

const VIBE_PRESETS = [
  "luz dorada",
  "neón",
  "blanco clínico",
  "naturaleza",
  "interior cálido",
  "skyline nocturno",
  "filmic grain",
  "shallow DOF",
  "handheld",
  "drone",
];

type Field = "tone" | "mood" | "visual_vibe";

export interface BriefBuilderProps {
  value: Partial<CreativeBrief>;
  onChange: (next: Partial<CreativeBrief>) => void;
  disabled?: boolean;
  defaultOpen?: boolean;
}

export function BriefBuilder({
  value,
  onChange,
  disabled,
  defaultOpen = false,
}: BriefBuilderProps) {
  const [open, setOpen] = useState(defaultOpen);
  const filled = countFilled(value);

  function toggle(field: Field, tag: string) {
    const current = (value[field] ?? []) as string[];
    const next = current.includes(tag)
      ? current.filter((t) => t !== tag)
      : [...current, tag];
    onChange({ ...value, [field]: next });
  }

  function addCustom(field: Field, raw: string) {
    const clean = raw.trim();
    if (!clean) return;
    const current = (value[field] ?? []) as string[];
    if (current.includes(clean)) return;
    onChange({ ...value, [field]: [...current, clean] });
  }

  return (
    <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] transition-colors">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Sliders className="size-4 text-violet-300" />
          Afinar contexto creativo
          {filled > 0 && (
            <span className="mono rounded-full bg-violet-500/15 px-2 py-0.5 text-[10px] text-violet-200">
              {filled} {filled === 1 ? "campo" : "campos"}
            </span>
          )}
        </span>
        <ChevronDown
          className={cn(
            "size-4 text-zinc-500 transition-transform duration-200",
            open && "rotate-180 text-zinc-300"
          )}
        />
      </button>

      {open && (
        <div className="flex flex-col gap-5 border-t border-white/[0.04] px-4 py-4">
          <p className="text-[11px] text-zinc-500">
            Todo opcional. Cuanto más rico el contexto, más afinado el guion y el shot plan.
          </p>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-zinc-400">Audiencia objetivo</label>
            <Input
              placeholder="Ej: founders early-stage, 25-40, hablan inglés y español"
              value={value.audience ?? ""}
              onChange={(e) => onChange({ ...value, audience: e.target.value })}
              disabled={disabled}
            />
          </div>

          <ChipSection
            label="Tono"
            field="tone"
            presets={TONE_PRESETS}
            selected={(value.tone ?? []) as string[]}
            onToggle={(t) => toggle("tone", t)}
            onAddCustom={(t) => addCustom("tone", t)}
            disabled={disabled}
          />

          <ChipSection
            label="Mood"
            field="mood"
            presets={MOOD_PRESETS}
            selected={(value.mood ?? []) as string[]}
            onToggle={(t) => toggle("mood", t)}
            onAddCustom={(t) => addCustom("mood", t)}
            disabled={disabled}
          />

          <ChipSection
            label="Vibra visual"
            field="visual_vibe"
            presets={VIBE_PRESETS}
            selected={(value.visual_vibe ?? []) as string[]}
            onToggle={(t) => toggle("visual_vibe", t)}
            onAddCustom={(t) => addCustom("visual_vibe", t)}
            disabled={disabled}
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-zinc-400">
                Paleta sugerida
              </label>
              <Input
                placeholder="Ej: warm amber, deep navy, off-white"
                value={value.palette ?? ""}
                onChange={(e) => onChange({ ...value, palette: e.target.value })}
                disabled={disabled}
              />
            </div>
            <div className="flex flex-col gap-2">
              <label className="text-xs font-medium text-zinc-400">Objetivo de CTA</label>
              <Input
                placeholder="Ej: visitar acme.com, suscribirse al boletín"
                value={value.cta_goal ?? ""}
                onChange={(e) => onChange({ ...value, cta_goal: e.target.value })}
                disabled={disabled}
              />
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-zinc-400">Notas extra</label>
            <Textarea
              rows={3}
              placeholder="Cualquier detalle suelto: producto, fecha, restricciones…"
              value={value.extra_notes ?? ""}
              onChange={(e) => onChange({ ...value, extra_notes: e.target.value })}
              disabled={disabled}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function ChipSection({
  label,
  presets,
  selected,
  onToggle,
  onAddCustom,
  disabled,
}: {
  label: string;
  field: Field;
  presets: string[];
  selected: string[];
  onToggle: (tag: string) => void;
  onAddCustom: (tag: string) => void;
  disabled?: boolean;
}) {
  const [custom, setCustom] = useState("");
  const all = Array.from(new Set([...presets, ...selected]));
  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium text-zinc-400">{label}</label>
      <div className="flex flex-wrap gap-1.5">
        {all.map((tag) => (
          <button
            key={tag}
            type="button"
            disabled={disabled}
            data-active={selected.includes(tag)}
            onClick={() => onToggle(tag)}
            className="chip"
          >
            {tag}
          </button>
        ))}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onAddCustom(custom);
            setCustom("");
          }}
          className="flex items-center"
        >
          <input
            type="text"
            value={custom}
            onChange={(e) => setCustom(e.target.value)}
            disabled={disabled}
            placeholder="+ añadir"
            className="h-7 w-24 rounded-full border border-dashed border-white/[0.12] bg-transparent px-3 text-xs text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-violet-400/60"
          />
        </form>
      </div>
    </div>
  );
}

function countFilled(b: Partial<CreativeBrief>): number {
  let n = 0;
  if (b.audience?.trim()) n += 1;
  if (b.palette?.trim()) n += 1;
  if (b.cta_goal?.trim()) n += 1;
  if (b.extra_notes?.trim()) n += 1;
  if ((b.tone ?? []).length) n += 1;
  if ((b.mood ?? []).length) n += 1;
  if ((b.visual_vibe ?? []).length) n += 1;
  return n;
}
