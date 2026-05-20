import { useEffect, useState } from "react";
import { AUTH_EVENT, clearToken, getToken, setToken } from "@/lib/auth";
import { api } from "@/lib/api";

export function useAuth() {
  const [token, setLocalToken] = useState<string | null>(() => getToken());

  useEffect(() => {
    const onChange = () => setLocalToken(getToken());
    window.addEventListener(AUTH_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(AUTH_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  return {
    token,
    isAuthenticated: token !== null,
    login: async (password: string) => {
      const resp = await api.login(password);
      setToken(resp.token, resp.expires_at);
    },
    logout: () => {
      clearToken();
    },
  };
}
