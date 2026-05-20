import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";

export function LoginForm() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!password) return;
    setLoading(true);
    try {
      await login(password);
      toast.success("Sesión iniciada");
      navigate("/", { replace: true });
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 429
            ? "Demasiados intentos. Espera 15 minutos."
            : "Contraseña incorrecta"
          : "Error inesperado";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] w-full items-center justify-center px-4">
      <Card className="w-full max-w-sm border-zinc-800/80">
        <CardContent className="flex flex-col gap-6 p-8 pt-8">
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="flex size-11 items-center justify-center rounded-xl bg-violet-500/15 text-violet-400">
              <Sparkles className="size-5" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight">Reels Factory</h1>
              <p className="mt-1 text-sm text-zinc-400">
                Introduce la contraseña para acceder
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="relative">
              <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-500" />
              <Input
                type="password"
                placeholder="Contraseña"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
                autoFocus
                className="pl-9"
              />
            </div>
            <Button type="submit" disabled={loading || !password} className="w-full">
              {loading ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Accediendo…
                </>
              ) : (
                "Acceder"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
