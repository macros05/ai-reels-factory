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
    <div className="relative flex min-h-[calc(100vh-4rem)] w-full items-center justify-center px-4">
      <div className="absolute -top-24 left-1/2 size-96 -translate-x-1/2 rounded-full bg-violet-500/20 blur-[120px]" />
      <div className="absolute bottom-0 right-12 size-72 rounded-full bg-cyan-400/10 blur-[100px]" />
      <Card className="relative w-full max-w-sm">
        <CardContent className="flex flex-col gap-7 p-8 pt-8">
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="relative flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500/40 via-violet-400/20 to-cyan-400/30 ring-1 ring-inset ring-white/10">
              <Sparkles className="size-6 text-violet-100" />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-zinc-50">
                <span className="text-gradient">Reels Factory</span>
              </h1>
              <p className="mt-1.5 text-sm text-zinc-400">
                Introduce la contraseña para acceder al studio
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
                className="pl-9 h-11"
              />
            </div>
            <Button
              type="submit"
              size="lg"
              disabled={loading || !password}
              className="ring-conic w-full"
            >
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
          <p className="mono text-center text-[10.5px] uppercase tracking-[0.18em] text-zinc-600">
            Higgsfield · Claude · ElevenLabs
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
