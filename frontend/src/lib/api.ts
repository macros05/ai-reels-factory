import type {
  Character,
  HiggsfieldStatus,
  LoginResponse,
  ProvidersResponse,
  Reference,
  ReferenceKind,
  RunDetail,
  RunSummary,
  ScriptOutput,
} from "@/types";
import { clearToken, getToken } from "./auth";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  { auth = true }: { auth?: boolean } = {}
): Promise<T> {
  const headers = new Headers(options.headers ?? {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const resp = await fetch(path, { ...options, headers });
  if (resp.status === 401 && auth) {
    clearToken();
    throw new ApiError(401, "Sesión expirada. Vuelve a iniciar sesión.");
  }
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const j = await resp.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  login: (password: string) =>
    request<LoginResponse>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify({ password }) },
      { auth: false }
    ),

  me: () => request<{ sub: string; exp: number }>("/api/auth/me"),

  providers: () => request<ProvidersResponse>("/api/providers"),

  listRuns: () => request<{ runs: RunSummary[] }>("/api/runs"),

  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),

  createRun: (input: {
    topic: string;
    provider?: string;
    draft?: boolean;
    runId?: string;
    soulId?: string | null;
  }) =>
    request<{ run_id: string; status: string; provider?: string }>(
      input.draft ? "/api/run/draft" : "/api/run",
      {
        method: "POST",
        body: JSON.stringify({
          topic: input.topic,
          ...(input.provider ? { provider: input.provider } : {}),
          ...(input.runId ? { run_id: input.runId } : {}),
          ...(input.soulId ? { soul_id: input.soulId } : {}),
        }),
      }
    ),

  higgsfieldStatus: () => request<HiggsfieldStatus>("/api/higgsfield/status"),

  listCharacters: () => request<{ characters: Character[] }>("/api/characters"),

  getCharacter: (soulId: string) =>
    request<Character>(`/api/characters/${soulId}`),

  uploadCharacterPhoto: async (
    file: File
  ): Promise<{ upload_id: string; local_path: string; bytes: number; mime: string }> => {
    const fd = new FormData();
    fd.append("file", file);
    return request("/api/characters/upload", { method: "POST", body: fd });
  },

  createCharacter: (input: {
    name: string;
    soul_model: "soul-2" | "soul-cinematic";
    image_uuids: string[];
    preview_path?: string | null;
  }) =>
    request<Character>("/api/characters", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  refreshCharacter: (soulId: string) =>
    request<Character>(`/api/characters/${soulId}/refresh`, { method: "POST" }),

  deleteCharacter: (soulId: string) =>
    request<{ deleted: string }>(`/api/characters/${soulId}`, { method: "DELETE" }),

  confirmRun: (runId: string, script: ScriptOutput) =>
    request<{ run_id: string; status: string }>(`/api/run/${runId}/confirm`, {
      method: "POST",
      body: JSON.stringify({ script }),
    }),

  uploadReference: async (
    runId: string,
    kind: ReferenceKind,
    file: File
  ): Promise<Reference> => {
    const fd = new FormData();
    fd.append("run_id", runId);
    fd.append("kind", kind);
    fd.append("file", file);
    return request<Reference>("/api/references", { method: "POST", body: fd });
  },

  addYoutubeReference: (
    runId: string,
    kind: "script" | "voice" | "music",
    url: string
  ) =>
    request<Reference>("/api/references/youtube", {
      method: "POST",
      body: JSON.stringify({ run_id: runId, kind, url }),
    }),

  listReferences: (runId: string) =>
    request<{ run_id: string; references: Reference[] }>(
      `/api/references/${runId}`
    ),
};

/** Build a media URL with the auth token in the query string so `<video>` can load it. */
export function mediaUrl(runId: string, filename: string): string {
  const token = getToken();
  return `/api/output/${runId}/${filename}${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}
