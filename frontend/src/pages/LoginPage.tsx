import { useEffect } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { LoginForm } from "@/components/auth/LoginForm";
import { Header } from "@/components/layout/Header";
import { useAuth } from "@/hooks/useAuth";

export function LoginPage() {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate("/", { replace: true });
  }, [isAuthenticated, navigate]);

  if (isAuthenticated) return <Navigate to="/" replace />;

  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">
        <LoginForm />
      </main>
    </div>
  );
}
