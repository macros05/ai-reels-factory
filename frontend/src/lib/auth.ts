const TOKEN_KEY = "reels.token";
const EXPIRES_KEY = "reels.token_expires_at";

export const AUTH_EVENT = "reels:auth-changed";

export function getToken(): string | null {
  const t = localStorage.getItem(TOKEN_KEY);
  if (!t) return null;
  const exp = localStorage.getItem(EXPIRES_KEY);
  if (exp && new Date(exp).getTime() < Date.now()) {
    clearToken();
    return null;
  }
  return t;
}

export function setToken(token: string, expiresAt: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EXPIRES_KEY, expiresAt);
  window.dispatchEvent(new Event(AUTH_EVENT));
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EXPIRES_KEY);
  window.dispatchEvent(new Event(AUTH_EVENT));
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}
