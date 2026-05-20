import { Link, NavLink, useNavigate } from "react-router-dom";
import { BookOpen, LogOut, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/lib/utils";

export function Header() {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-white/[0.05] bg-[color:var(--color-ink-950)]/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-2.5">
          <div className="relative flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 via-violet-400/15 to-cyan-400/20 text-violet-100 ring-1 ring-inset ring-white/10 transition-all group-hover:ring-violet-300/30">
            <Sparkles className="size-4" />
          </div>
          <div className="flex flex-col leading-none">
            <span className="text-sm font-semibold tracking-tight text-zinc-50">
              Reels Factory
            </span>
            <span className="mono text-[10px] uppercase tracking-[0.18em] text-zinc-500">
              Higgsfield · Claude
            </span>
          </div>
        </Link>
        {isAuthenticated && (
          <div className="flex items-center gap-1">
            <NavLink
              to="/help"
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-all",
                  isActive
                    ? "bg-white/[0.06] text-zinc-50"
                    : "text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-200"
                )
              }
            >
              <BookOpen className="size-3.5" />
              <span className="hidden sm:inline">Ayuda</span>
            </NavLink>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              <LogOut className="size-3.5" />
              <span className="hidden sm:inline">Cerrar sesión</span>
            </Button>
          </div>
        )}
      </div>
    </header>
  );
}
