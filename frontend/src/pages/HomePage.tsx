import { useState } from "react";
import { Activity, Coins, ShieldCheck, Sparkles, Users } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { CharactersPanel } from "@/components/characters/CharactersPanel";
import { GalleryGrid } from "@/components/runs/GalleryGrid";
import { RunForm } from "@/components/runs/RunForm";
import { useHiggsfieldStatus } from "@/hooks/useCharacters";
import { useRuns } from "@/hooks/useRuns";
import { cn, formatCredits } from "@/lib/utils";

type Tab = "create" | "characters";

export function HomePage() {
  const { data: runs, isLoading } = useRuns();
  const { data: hf } = useHiggsfieldStatus();
  const [tab, setTab] = useState<Tab>("create");

  return (
    <div className="relative-layer flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        <section className="mb-10 flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-zinc-400">
              <Sparkles className="size-3 text-violet-300" />
              Studio · v0.3
            </div>
            <h1 className="text-balance text-4xl font-semibold tracking-tight text-zinc-50 sm:text-5xl">
              <span className="text-gradient">Reels cinematográficos</span>
              <br className="hidden sm:block" />
              dirigidos por Claude.
            </h1>
            <p className="max-w-2xl text-[15px] leading-relaxed text-zinc-400">
              Le pasas un brief — el tema, el público, el mood, las referencias —
              y obtienes un guion editable, un plan de rodaje frame-by-frame y
              un MP4 vertical listo para publicar. Higgsfield ejecuta, Claude
              dirige.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            <HiggsfieldStatusCard
              authenticated={hf?.authenticated}
              credits={hf?.account?.credits}
              plan={hf?.account?.plan}
              email={hf?.account?.email}
            />
            <StatCard
              icon={Activity}
              label="Runs"
              value={runs ? String(runs.length) : "—"}
              tone="violet"
            />
            <StatCard
              icon={Users}
              label="Characters disponibles"
              value="Soul-ID"
              tone="cyan"
              hint="entrena en la pestaña Characters"
            />
          </div>
        </section>

        <div className="mb-8 flex gap-1 border-b border-white/[0.06]">
          {[
            { id: "create" as const, label: "Crear reel" },
            { id: "characters" as const, label: "Characters" },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "relative -mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-all",
                tab === t.id
                  ? "border-violet-400 text-zinc-50"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "create" ? (
          <>
            <section className="mb-14">
              <RunForm />
            </section>

            <section className="flex flex-col gap-4">
              <div className="flex items-baseline justify-between">
                <h2 className="text-xl font-semibold tracking-tight text-zinc-100">
                  Tus reels
                </h2>
                {runs && (
                  <span className="mono text-xs text-zinc-500">
                    {runs.length} {runs.length === 1 ? "run" : "runs"}
                  </span>
                )}
              </div>
              <GalleryGrid runs={runs} loading={isLoading} />
            </section>
          </>
        ) : (
          <section>
            <CharactersPanel />
          </section>
        )}
      </main>
    </div>
  );
}

function HiggsfieldStatusCard({
  authenticated,
  credits,
  plan,
  email,
}: {
  authenticated?: boolean;
  credits?: number;
  plan?: string;
  email?: string;
}) {
  if (authenticated === undefined) {
    return (
      <div className="glass flex items-center gap-3 rounded-2xl p-4">
        <div className="size-9 animate-pulse rounded-full bg-white/[0.04]" />
        <div className="space-y-1">
          <div className="h-3 w-24 animate-pulse rounded bg-white/[0.04]" />
          <div className="h-2.5 w-32 animate-pulse rounded bg-white/[0.03]" />
        </div>
      </div>
    );
  }
  if (!authenticated) {
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/[0.06] p-4">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-rose-300">
          <ShieldCheck className="size-3.5" /> CLI sin autenticar
        </div>
        <p className="mt-2 text-sm text-rose-100">
          Ejecuta{" "}
          <code className="mono rounded bg-rose-500/15 px-1.5 py-0.5 text-[12px]">
            higgsfield auth login
          </code>{" "}
          en el host.
        </p>
      </div>
    );
  }
  return (
    <div className="glass relative overflow-hidden rounded-2xl p-4">
      <div className="absolute -right-10 -top-12 size-40 rounded-full bg-emerald-500/10 blur-3xl" />
      <div className="relative flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-300 ring-1 ring-inset ring-emerald-400/20">
          <Coins className="size-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[11px] font-medium uppercase tracking-wider text-emerald-300/80">
            Higgsfield · {plan ?? "—"}
          </span>
          <span className="mono text-sm font-semibold text-zinc-50">
            {formatCredits(credits ?? null)}
          </span>
          <span className="mono mt-0.5 text-[10.5px] text-zinc-500">{email ?? ""}</span>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  tone,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  tone: "violet" | "cyan";
  hint?: string;
}) {
  const ring =
    tone === "violet"
      ? "from-violet-500/30 via-violet-400/15 to-transparent text-violet-200 ring-violet-400/20"
      : "from-cyan-400/25 via-cyan-300/10 to-transparent text-cyan-200 ring-cyan-300/20";
  return (
    <div className="glass relative overflow-hidden rounded-2xl p-4">
      <div className="absolute -right-12 -top-12 size-36 rounded-full bg-gradient-to-br from-white/5 to-transparent blur-3xl" />
      <div className="relative flex items-center gap-3">
        <div
          className={cn(
            "flex size-9 items-center justify-center rounded-xl bg-gradient-to-br ring-1 ring-inset",
            ring
          )}
        >
          <Icon className="size-4" />
        </div>
        <div className="flex flex-col">
          <span className="text-[11px] font-medium uppercase tracking-wider text-zinc-400">
            {label}
          </span>
          <span className="mono text-sm font-semibold text-zinc-50">{value}</span>
          {hint && (
            <span className="mt-0.5 text-[10.5px] text-zinc-500">{hint}</span>
          )}
        </div>
      </div>
    </div>
  );
}
