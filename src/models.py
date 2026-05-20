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
