import { Link, useNavigate } from "react-router-dom";
import { LogOut, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";

export function Header() {
  const { isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-900 bg-zinc-950/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-md bg-violet-500/15 text-violet-400 transition-colors group-hover:bg-violet-500/25">
            <Sparkles className="size-4" />
          </div>
          <span className="text-sm font-semibold tracking-tight">Reels Factory</span>
        </Link>
        {isAuthenticated && (
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
        )}
      </div>
    </header>
  );
}
