import { toast } from "sonner";

export function HashtagChips({ hashtags }: { hashtags: string[] }) {
  if (!hashtags.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium text-zinc-300">Hashtags</label>
      <div className="flex flex-wrap gap-1.5">
        {hashtags.map((h) => {
          const tag = `#${h.replace(/^#/, "")}`;
          return (
            <button
              key={h}
              type="button"
              onClick={async () => {
                await navigator.clipboard.writeText(tag);
                toast.success(`Copiado ${tag}`);
              }}
              className="rounded-md border border-zinc-800 bg-zinc-900/40 px-2 py-0.5 text-xs text-zinc-300 transition-colors hover:border-violet-500/50 hover:bg-violet-500/10 hover:text-violet-300"
            >
              {tag}
            </button>
          );
        })}
      </div>
    </div>
  );
}
