import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { CharactersPanel } from "@/components/characters/CharactersPanel";
import { GalleryGrid } from "@/components/runs/GalleryGrid";
import { RunForm } from "@/components/runs/RunForm";
import { useHiggsfieldStatus } from "@/hooks/useCharacters";
import { useRuns } from "@/hooks/useRuns";
import { formatCredits, cn } from "@/lib/utils";

type Tab = "create" | "characters";

export function HomePage() {
  const { data: runs, isLoading } = useRuns();
  const { data: hf } = useHiggsfieldStatus();
  const [tab, setTab] = useState<Tab>("create");

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        <section className="mb-6 flex flex-wrap items-end justify-between gap-3">
          <div className="max-w-2xl">
            <h1 className="text-2xl font-semibold tracking-tight text-zinc-50 sm:text-3xl">
              Genera reels
            </h1>
            <p className="mt-2 text-sm text-zinc-400">
              Un tema. Treinta segundos. Listo para Instagram.
            </p>
          </div>
          <HiggsfieldStatusBadge
            authenticated={hf?.authenticated}
            credits={hf?.account?.credits}
            plan={hf?.account?.plan}
            email={hf?.account?.email}
          />
        </section>

        <div className="mb-6 flex gap-1 border-b border-zinc-800">
          {(
            [
              { id: "create" as const, label: "Crear" },
              { id: "characters" as const, label: "Characters" },
            ]
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={cn(
                "relative -mb-px border-b-2 px-3 py-2 text-sm font-medium transition-colors",
                tab === t.id
                  ? "border-violet-500 text-zinc-100"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {tab === "create" ? (
          <>
            <section className="mb-12">
              <RunForm />
            </section>

            <section className="flex flex-col gap-4">
              <div className="flex items-baseline justify-between">
                <h2 className="text-lg font-semibold tracking-tight text-zinc-100">
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

function HiggsfieldStatusBadge({
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
      <div className="rounded-md border border-zinc-800 bg-zinc-900/40 px-3 py-2 text-xs text-zinc-500">
        Higgsfield…
      </div>
    );
  }
  if (!authenticated) {
    return (
      <div className="rounded-md border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
        Higgsfield CLI sin autenticar — ejecuta{" "}
        <code className="mono">higgsfield auth login</code> en el host
      </div>
    );
  }
  return (
    <div className="flex flex-col items-end gap-0.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-right">
      <span className="text-xs font-medium text-emerald-300">
        Higgsfield · {plan ?? "—"}
      </span>
      <span className="mono text-[11px] text-emerald-200/80">
        {formatCredits(credits ?? null)} · {email ?? ""}
      </span>
    </div>
  );
}
