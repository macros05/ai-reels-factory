"""Pydantic data models used across the pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SCRIPT_READY = "script_ready"
    DONE = "done"
    FAILED = "failed"


ReferenceKind = Literal["persona", "style", "script", "voice", "music"]


class Reference(BaseModel):
    """A user-supplied input that shapes the generated reel.

    `kind` tells the pipeline which step consumes it:
      - persona  → video_generator switches to image-to-video on this image
      - style    → style_extractor describes it; the brief is appended to prompts
      - script   → script_generator borrows angle/structure from the transcript
      - voice    → voice_generator clones this audio via ElevenLabs IVC
      - music    → assembler mixes this audio under the voiceover as score bed
    """

    kind: ReferenceKind
    path: Path
    source_url: str | None = None
    mime: str
    bytes: int


class CreativeBrief(BaseModel):
    """Optional structured brief the user can attach to a topic.

    Everything is optional — a bare topic still works — but when provided it
    pushes the script generator and the director toward a much sharper output
    than free-text alone could. Concatenated into the user prompt for Claude,
    so every field maps to natural-language guidance.
    """

    topic: str
    audience: str | None = None
    tone: list[str] = Field(default_factory=list)
    mood: list[str] = Field(default_factory=list)
    visual_vibe: list[str] = Field(default_factory=list)
    palette: str | None = None
    cta_goal: str | None = None
    extra_notes: str | None = None


class Shot(BaseModel):
    """A single shot in the director's frame-by-frame plan.

    Each shot maps 1:1 to a clip the video provider generates. The director
    fills in concrete cinematography (shot size, lens, camera move, lighting)
    plus a time-coded action breakdown so the model has unambiguous direction.
    """

    index: int
    shot_size: Literal[
        "extreme_close_up",
        "close_up",
        "medium_close_up",
        "medium",
        "medium_wide",
        "wide",
        "extreme_wide",
    ] = "medium_close_up"
    camera_move: str = "handheld push-in"
    lens_mm: int = 35
    aperture: str = "f/2.0"
    lighting: str = "soft natural daylight, warm key, gentle fill"
    location: str = ""
    wardrobe: str = ""
    props: list[str] = Field(default_factory=list)
    action_beats: list[str] = Field(default_factory=list)
    dialogue_excerpt: str = ""
    emotion: str = "calm, grounded"
    color_palette: str = ""
    transition_in: str = "hard cut"
    transition_out: str = "hard cut"
    duration_seconds: float = 5.0
    # The fully-composed prompt the video generator should send to Higgsfield.
    # If empty, the video step falls back to script.visual_prompts[index].
    final_prompt: str = ""


class ShotPlan(BaseModel):
    """The full director's plan for a reel."""

    title: str = ""
    logline: str = ""
    style_brief: str = ""
    persona_lock: str = ""
    shots: list[Shot] = Field(default_factory=list)


class ScriptOutput(BaseModel):
    """Output of the script generation step."""

    hook: str
    body: str
    cta: str
    full_script: str
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    visual_prompts: list[str] = Field(default_factory=list)
    persona_description: str = ""
    persona_gender: Literal["female", "male"] = "female"


class VoiceOutput(BaseModel):
    audio_path: Path
    duration_seconds: float


class SubtitleSegment(BaseModel):
    start: float
    end: float
    text: str


class SubtitleOutput(BaseModel):
    srt_path: Path
    segments: list[SubtitleSegment]


class AssembledOutput(BaseModel):
    final_video_path: Path


class RunResult(BaseModel):
    run_id: str
    topic: str
    status: RunStatus = RunStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    error: str | None = None
    output_dir: Path
    final_video_path: Path | None = None
    caption_path: Path | None = None
    script: ScriptOutput | None = None
    provider: str | None = None
    current_step: str | None = None
    references: list[Reference] = Field(default_factory=list)
    # Higgsfield Soul ID selected for the run, if any. When set, the video
    # step generates one persona still per clip via text2image_soul_v2 +
    # soul_id and feeds it as --start-image, locking the face across clips.
    soul_id: str | None = None
    # When true, the ElevenLabs voice step is skipped entirely so the reel
    # ends up music-only (matches Apple/Holded brand-video aesthetics). We
    # persist this on the run so /run/draft + /confirm preserve the choice
    # across the SCRIPT_READY pause — resume() reads it back when rebuilding
    # context.
    voiceless: bool = False
    # When true, generate one Nano-Banana-Pro keyframe per clip (free on
    # the Ultra plan) and feed it as --start-image to the video provider.
    # Trades a few seconds of image-gen for radically better composition
    # control than pure text-to-video. Persisted alongside voiceless so the
    # /confirm flow propagates it.
    use_keyframes: bool = False
    # Director's frame-by-frame plan. Populated by DirectorStep after the
    # script step; consumed by video_generator to feed Higgsfield. Optional
    # so legacy runs without a plan still load.
    shot_plan: ShotPlan | None = None
    # Structured brief, when provided. Persisted so the editor and the
    # detail view can show what context drove the run.
    brief: CreativeBrief | None = None


CharacterStatus = Literal["training", "ready", "failed"]


class Character(BaseModel):
    """A Higgsfield Soul-ID trained on the user's photos.

    Stored locally in `data/characters.db`; the underlying Soul lives in
    Higgsfield's cloud and survives DB resets. Trained once, reusable across
    every reel — solves the "same face, different reel" problem.
    """

    soul_id: str
    name: str
    status: CharacterStatus = "training"
    soul_model: Literal["soul-2", "soul-cinematic"] = "soul-2"
    image_uuids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ready_at: datetime | None = None
    error: str | None = None
    # Optional preview image (any one of the training photos) for the UI.
    preview_path: Path | None = None
