export type RunStatus = "pending" | "running" | "script_ready" | "done" | "failed";

export type ReferenceKind = "persona" | "style" | "script" | "voice" | "music";

export interface Reference {
  kind: ReferenceKind;
  path: string;
  source_url: string | null;
  mime: string;
  bytes: number;
}

export type Provider = "veo" | "kling" | "seedance";

export interface ProviderInfo {
  id: Provider;
  name: string;
  tier: "Económico" | "Equilibrado" | "Premium";
  model_id: string;
  native_audio: boolean;
  supports_persona: boolean;
  supports_soul_id: boolean;
  clips: number;
  clip_duration: number;
  total_duration: number;
  cost_credits: number;
}

export interface ProvidersResponse {
  current: Provider;
  available: ProviderInfo[];
}

export interface ScriptOutput {
  hook: string;
  body: string;
  cta: string;
  full_script: string;
  caption: string;
  hashtags: string[];
  visual_prompts: string[];
  persona_description: string;
  persona_gender: "female" | "male";
}

export type ShotSize =
  | "extreme_close_up"
  | "close_up"
  | "medium_close_up"
  | "medium"
  | "medium_wide"
  | "wide"
  | "extreme_wide";

export interface Shot {
  index: number;
  shot_size: ShotSize;
  camera_move: string;
  lens_mm: number;
  aperture: string;
  lighting: string;
  location: string;
  wardrobe: string;
  props: string[];
  action_beats: string[];
  dialogue_excerpt: string;
  emotion: string;
  color_palette: string;
  transition_in: string;
  transition_out: string;
  duration_seconds: number;
  final_prompt: string;
}

export interface ShotPlan {
  title: string;
  logline: string;
  style_brief: string;
  persona_lock: string;
  camera_directive: string;
  shots: Shot[];
}

export interface CreativeBrief {
  topic: string;
  audience: string | null;
  tone: string[];
  mood: string[];
  visual_vibe: string[];
  palette: string | null;
  cta_goal: string | null;
  extra_notes: string | null;
}

export interface RunSummary {
  run_id: string;
  topic: string;
  status: RunStatus;
  created_at: string;
  finished_at: string | null;
  error: string | null;
  provider: Provider | null;
  current_step: string | null;
  cost_credits: number | null;
  soul_id: string | null;
  has_video: boolean;
}

export interface RunDetail extends RunSummary {
  script: ScriptOutput | null;
  shot_plan: ShotPlan | null;
  brief: CreativeBrief | null;
  caption: string | null;
}

export interface LoginResponse {
  token: string;
  expires_at: string;
}

export type CharacterStatus = "training" | "ready" | "failed";

export interface Character {
  soul_id: string;
  name: string;
  status: CharacterStatus;
  soul_model: "soul-2" | "soul-cinematic";
  image_uuids: string[];
  created_at: string;
  ready_at: string | null;
  error: string | null;
  preview_path: string | null;
}

export interface HiggsfieldAccount {
  email?: string;
  plan?: string;
  credits?: number;
}

export interface HiggsfieldStatus {
  authenticated: boolean;
  account?: HiggsfieldAccount;
  error?: string;
}
