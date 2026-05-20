"""Application configuration loaded from environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VideoProvider = Literal["veo", "kling", "seedance", "cinematic_studio_v2"]


class Settings(BaseSettings):
    """Runtime configuration loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", alias="ELEVENLABS_VOICE_ID")
    # Gender-matched voice IDs (defaults are ElevenLabs preset multilingual voices:
    # Laura = warm female, George = mature male). Override via env if you have premium IDs.
    elevenlabs_voice_id_female: str = Field(
        default="FGY2WhTYpPnrIDTdsKH5", alias="ELEVENLABS_VOICE_ID_FEMALE"
    )
    elevenlabs_voice_id_male: str = Field(
        default="JBFqnCBsd6RMkjVDRZzb", alias="ELEVENLABS_VOICE_ID_MALE"
    )

    # Higgsfield is wired via the official CLI (browser device-flow auth), not
    # an API key. Run `higgsfield auth login` once on the host; the token is
    # stored under ~/.higgsfield. See docs/HIGGSFIELD_API.md for setup.
    higgsfield_cli_path: str = Field(default="higgsfield", alias="HF_CLI_PATH")

    video_provider: VideoProvider = Field(default="seedance", alias="VIDEO_PROVIDER")

    app_password: str = Field(default="changeme", alias="APP_PASSWORD")
    jwt_secret: str = Field(
        default="dev-only-secret-do-not-use-in-production-please-please-please",
        alias="JWT_SECRET",
    )
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 7

    anthropic_model: str = "claude-sonnet-4-5"
    # eleven_v3 is ElevenLabs' most expressive/natural model. Override via env if needed.
    elevenlabs_model: str = Field(default="eleven_v3", alias="ELEVENLABS_MODEL")
    # 128 kbps is the highest mp3 available on the ElevenLabs Free tier;
    # mp3_44100_192 requires Creator and above and 403s otherwise. Set
    # ELEVENLABS_OUTPUT_FORMAT=mp3_44100_192 in .env if your account is upgraded.
    elevenlabs_output_format: str = Field(
        default="mp3_44100_128", alias="ELEVENLABS_OUTPUT_FORMAT"
    )
    # eleven_v3 in Spanish reads cleanest with low stability + meaty style: the
    # voice gets dynamic intonation instead of the flat newsreader cadence the
    # defaults produce. Tuned by ear against the previous 0.45 / 0.85 / 0.35.
    elevenlabs_stability: float = 0.35
    elevenlabs_similarity_boost: float = 0.90
    elevenlabs_style: float = 0.55
    elevenlabs_use_speaker_boost: bool = True

    # Suffix appended to every video prompt to force motion + cinematic camera work.
    motion_prompt_suffix: str = (
        "dynamic handheld camera, smooth dolly movement, energetic micro-actions, "
        "natural body movement, subtle parallax, cinematic motion, 9:16 vertical, "
        "hyperrealistic, shot on Sony FX3, shallow depth of field, natural lighting"
    )
    motion_negative_prompt: str = (
        "static, frozen, motionless, still image, slideshow, posed mannequin, "
        "lifeless, low quality, blurry, deformed hands, watermark, text overlay"
    )

    # Higgsfield CLI `job_set_type` strings (one per provider). All overridable
    # via env because Higgsfield ships new revisions on a faster cadence than
    # this file gets updated. `higgsfield model list` is the live catalog.
    veo_model: str = Field(default="veo3_1", alias="HF_VEO_MODEL")
    kling_model: str = Field(default="kling3_0", alias="HF_KLING_MODEL")
    seedance_model: str = Field(default="seedance_2_0", alias="HF_SEEDANCE_MODEL")
    cinematic_studio_model: str = Field(
        default="cinematic_studio_video_v2", alias="HF_CINEMATIC_STUDIO_MODEL"
    )
    # Image generator used to materialise a Soul-ID persona still per clip
    # before feeding it into the video model as --start-image.
    soul_image_model: str = Field(
        default="text2image_soul_v2", alias="HF_SOUL_IMAGE_MODEL"
    )
    # Per-provider quality knobs. Defaults are chosen to look good in 9:16
    # without being needlessly expensive.
    kling_mode: str = Field(default="pro", alias="HF_KLING_MODE")  # pro | std | 4k
    seedance_mode: str = Field(default="std", alias="HF_SEEDANCE_MODE")  # std | fast
    seedance_resolution: str = Field(
        default="1080p", alias="HF_SEEDANCE_RESOLUTION"
    )  # 480p | 720p | 1080p
    veo_quality: str = Field(default="basic", alias="HF_VEO_QUALITY")  # basic | high | ultra
    veo_variant: str = Field(default="veo-3-1-fast", alias="HF_VEO_VARIANT")
    # cinematic_studio_video_v2: 'std' costs 7 cr / 5s clip, 'pro' costs 10 cr.
    # We default to std so a 6-clip reel lands at ~42 cr (under the user's
    # explicit 60 cr cap); flip to pro via env when sharper motion matters
    # more than budget.
    cinematic_studio_mode: str = Field(
        default="std", alias="HF_CINEMATIC_STUDIO_MODE"
    )  # std | pro
    # Higgsfield "genre" tag biases the motion model toward a tonal register.
    # `intimate` matches a warm Apple-ish reel aesthetic;
    # use `spectacle` for product-launch energy, `auto` to let the model decide.
    cinematic_studio_genre: str = Field(
        default="intimate", alias="HF_CINEMATIC_STUDIO_GENRE"
    )  # auto | action | horror | comedy | western | suspense | intimate | spectacle

    veo_clip_duration: int = 8
    veo_num_clips: int = 3
    standard_clip_duration: int = 5
    standard_num_clips: int = 5

    video_width: int = 1080
    video_height: int = 1920

    output_dir: Path = Path("output")
    # User-uploaded reference files (persona photos, style images/videos,
    # script transcripts, voice samples). Each run gets a subdir keyed by run_id.
    references_dir: Path = Path("output/_uploads")
    # Persistent app data outside output/. Bind-mounted in prod from the host
    # so it survives an output cleanup. Contains characters.db + character
    # photo uploads.
    data_dir: Path = Path("data")
    # Whether to keep ElevenLabs cloned voices after the run completes. Default
    # False so we don't litter the user's voice library — flip to True only
    # when debugging.
    voice_clone_keep: bool = False
    # YouTube ingestion limits — keep voice samples short (good IVC sweet spot)
    # and transcripts bounded.
    youtube_voice_sample_seconds: int = 60
    youtube_transcript_max_chars: int = 20000
    # "small" handles Spanish notably better than "base"; "base" mangles acronyms
    # (e.g. "RRHH" → "rerlos ocho saches") and homonyms.
    whisper_model: str = "small"
    language: str = "es"

    frontend_dist: Path = Path("frontend/dist")

    # Subtitle styling (ASS / libass). Karaoke-style 1-3 word chunks, lower third.
    subtitle_font: str = "Montserrat Black"
    subtitle_font_size: int = 22
    subtitle_primary_colour: str = "&H00FFFFFF"
    subtitle_outline_colour: str = "&H00000000"
    subtitle_back_colour: str = "&H00000000"
    subtitle_outline: float = 3.5
    subtitle_shadow: float = 0.6
    subtitle_margin_v: int = 260
    subtitle_max_words_per_chunk: int = 3

    @field_validator("veo_clip_duration")
    @classmethod
    def _veo_duration_must_be_4_6_or_8(cls, v: int) -> int:
        # Higgsfield veo3_1 only accepts duration literals '4'|'6'|'8'.
        # Catch a misconfigured .env at startup instead of at first run.
        if v not in {4, 6, 8}:
            raise ValueError(
                f"veo_clip_duration must be one of 4, 6 or 8 (Veo hard limit), got {v}"
            )
        return v

    def clip_count(self) -> int:
        return self.clip_count_for(self.video_provider)

    def clip_duration(self) -> int:
        return self.clip_duration_for(self.video_provider)

    def clip_count_for(self, provider: VideoProvider) -> int:
        return self.veo_num_clips if provider == "veo" else self.standard_num_clips

    def clip_duration_for(self, provider: VideoProvider) -> int:
        return self.veo_clip_duration if provider == "veo" else self.standard_clip_duration

    def cli_model_for(self, provider: VideoProvider) -> str:
        return {
            "veo": self.veo_model,
            "kling": self.kling_model,
            "seedance": self.seedance_model,
            "cinematic_studio_v2": self.cinematic_studio_model,
        }[provider]


# Approximate credit cost per reel.
# Real meter lives at `higgsfield account transactions` — these are
# placeholders until we audit the first paid run.
PROVIDER_COST_CREDITS: dict[VideoProvider, int] = {
    "seedance": 50,
    "kling": 250,
    "veo": 1200,
    # cinematic_studio_v2 @ std mode = ~7 cr × 6 clips = 42 cr; pro mode would be 60.
    "cinematic_studio_v2": 45,
}


settings = Settings()
