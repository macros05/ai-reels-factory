# Sprint: references + editor + max-quality (ai-reels-factory)

Self-contained brief for executing the references sprint in a fresh Claude Code
session. The codebase lives at `/opt/ai-reels-factory/` and the running service
is `reels-factory.service` (systemd). Tests run with `uv run pytest`.

## Goal

Add four kinds of user-supplied references that shape the generated reel, plus
an inline editor that pauses the pipeline after script generation so the user
can tweak hook / body / CTA / visual prompts / hashtags before voice & video
are rendered. Reels never carry subtitles. Always pick the best-available
model tier.

## References

| Letter | Input from user | Effect on output |
|---|---|---|
| **A — Persona** | one or more images (jpg/png, ≤8 MB ea., min 512px) | Pipeline switches `video_generator` to `image-to-video` models so every clip features the same person. Veo provider is disabled when persona refs are supplied (no i2v variant). |
| **B — Estilo** | image OR short video (≤15 s, ≤25 MB) | Claude Vision (anthropic vision API) writes a 50-80 word style brief (palette, lighting, lens, composition, mood). The brief is appended to every `visual_prompt`. |
| **C — Guion** | one or more YouTube URLs | `yt-dlp --skip-download --write-auto-sub --sub-lang es,en --write-info-json` extracts transcript + title + description. We pass the transcript verbatim and the title/description as context to Claude in `script_generator`, asking it to **borrow angle and structure, not copy words**. |
| **D — Voz** | YouTube URL OR audio file (mp3/wav, 10 s – 5 min) | ElevenLabs Instant Voice Cloning (`POST /v1/voices/add`). On success we get a temporary `voice_id`. `voice_generator` uses that id instead of the gender-matched preset. The cloned voice is **deleted** at the end of the run (`DELETE /v1/voices/{voice_id}`) to keep the user's voice library clean. |

References are optional — zero, one, or several can be attached per run.

## Editor flow

Replace the single-shot `POST /api/run` with two phases:

1. `POST /api/run/draft` — kicks off `script_generator` only, returns `{run_id, script}` after Claude responds. State: `script_ready`.
2. `POST /api/run/{id}/confirm` — body carries the (possibly edited) `script` object. Voice / video / lipsync / assembler run from here. State transitions: `script_ready → running → done|failed`.

Optional shortcut: `POST /api/run` (keeps current behaviour for backward compat) sends a flag `skip_editor=true` and goes straight through.

## Quality posture (continues from prior sprints)

Already in place:
- `mp3_44100_192` ElevenLabs output, expressive `voice_settings`.
- `seedance/v1/pro` for t2v, `lipsync-2-pro` for sync.
- `crf=18 preset=slow loudnorm=-14 LUFS` in ffmpeg assembler.
- `script_generator` soft-cap; `voice_generator` atempo-fits audio to timeline; `_slice_audio` pads short audio.
- No subtitles. `subtitle_generator` no longer runs in the pipeline.

Add for this sprint:
- When persona refs are present, use `fal-ai/kling-video/v2.6/pro/image-to-video` and `fal-ai/bytedance/seedance/v1/pro/image-to-video` (the i2v counterparts of the current text-to-video models).

## File-level changes

### Backend

- `src/models.py`
  - Add `ReferenceKind = Literal["persona","style","script","voice"]`.
  - Add `Reference(BaseModel)`: `kind`, `path` (Path, server-local), `source_url` (optional, for YouTube), `mime`, `bytes`.
  - Extend `RunResult` with `references: list[Reference]` and `status` enum: add `SCRIPT_READY = "script_ready"`.

- `src/config.py`
  - Add `kling_i2v_model: str = "fal-ai/kling-video/v2.6/pro/image-to-video"` and `seedance_i2v_model: str = "fal-ai/bytedance/seedance/v1/pro/image-to-video"`.
  - Add `references_dir: Path = output_dir / "_uploads"` for persistent storage of uploaded files.
  - Add `voice_clone_keep: bool = False` (set True if you want to retain cloned voices).

- `src/api/main.py`
  - New endpoint `POST /api/references` (multipart upload, kind=...). Returns a `Reference` JSON with the server path.
  - New endpoint `POST /api/references/youtube` (json: `{kind: "script"|"voice", url: "..."}`). Server downloads audio (for `voice`) or subtitles (for `script`) via `yt-dlp`. Returns `Reference`.
  - Refactor `POST /api/run` into `draft` + `confirm`, plus keep a `skip_editor` shortcut.
  - Wire `references` into the background-task `_execute_run`.

- `src/pipeline.py`
  - Accept `references: list[Reference]` and `skip_editor: bool`.
  - When `skip_editor=False`, run only `script_generator`, persist `status=script_ready`, and return. A separate `Pipeline.resume(run_id, edited_script)` continues from voice/video.
  - When persona refs are present and provider is veo → switch to kling.

- `src/steps/script_generator.py`
  - When a `script` reference is present, fetch the transcript text (already on disk) and prepend it to the user prompt: *"Tienes esta transcripción como referencia. Toma el ángulo, el hook y la estructura. **No copies frases literales**."*

- `src/steps/voice_generator.py`
  - When a `voice` reference is present, call `client.voices.ivc.create(name=f"reel-{run_id}", files=[ref.path])`, use the returned `voice_id`, and remember to delete it in a `finally`.

- `src/steps/video_generator.py`
  - When persona refs are present:
    - `kling`: use `kling_i2v_model`, args `{"prompt", "image_url", "duration", "aspect_ratio": "9:16"}` (image uploaded via `fal_client.upload_file_async`).
    - `seedance`: use `seedance_i2v_model`, args `{"prompt", "image_url", "duration", "aspect_ratio": "9:16", "resolution": "1080p"}`.
    - rotate persona images round-robin if user supplied >1.

- New `src/steps/style_extractor.py`
  - Anthropic vision call: send up to 3 style refs (images; for videos pull frame 1/3 and 2/3 with ffmpeg first), prompt Claude to write a 60-word visual brief.
  - Brief is stored in `context["style_brief"]` and appended to each `visual_prompt` before video generation.

- `src/utils/youtube.py` (new)
  - `fetch_transcript(url) -> Path`: writes `.txt` of the auto-sub or human sub.
  - `fetch_audio_sample(url, max_seconds=60) -> Path`: downloads bestaudio → mp3 with `yt-dlp + ffmpeg`, capped at 60 s to fit ElevenLabs IVC sweet-spot.

### Frontend (React)

- `frontend/src/components/runs/ReferenceUploader.tsx` (new): 4 tabs (Persona / Estilo / Guion / Voz), file picker + URL field per tab.
- `frontend/src/components/runs/ScriptEditor.tsx` (new): editable fields for hook/body/cta/hashtags, list of editable visual prompts, "Confirmar y generar" button.
- `frontend/src/components/runs/RunForm.tsx`: add references uploader, hide submit and show editor when `status == script_ready`.
- `frontend/src/types.ts`: extend `RunStatus` with `script_ready`, add `Reference` type.
- `frontend/src/hooks/useDraftRun.ts`, `useConfirmRun.ts`, `useUploadReference.ts`.

### Tests

- `tests/test_references.py`
  - Upload returns 200, persists file under `output_dir/_uploads/`.
  - Persona reference → video_generator dispatches to i2v model with `image_url` set.
  - Voice reference → voice_generator calls IVC and uses returned id; teardown deletes id.
  - Script reference → transcript is included in script_generator prompt.
  - Style reference → style_brief is non-empty and appended to each visual prompt.
- `tests/test_pipeline.py`
  - Draft → script persisted, status=script_ready, no voice/video calls.
  - Confirm with edited script → pipeline resumes, edited content reaches voice & video.

### Ops

- Add `yt-dlp` to `pyproject.toml` dependencies.
- Add `anthropic[vision]` (or ensure existing `anthropic` SDK version supports image content blocks).
- Restart `reels-factory.service` after merging to main.

## Cost notes

- Kling i2v ≈ same as t2v ($3.10).
- Seedance i2v ≈ $3.20.
- ElevenLabs IVC requires Creator plan or above (free on Pro). Cloning itself is free, generation is the usual per-char cost.
- Anthropic vision: a 60-word style brief from 3 images ≈ $0.01 per run.

## Acceptance criteria

A run made with:
- 1 persona image,
- 1 YouTube URL as script ref,
- 1 audio file as voice ref,
- 1 style image,

…produces a 25 s, 1080×1920, no-subtitle reel where:
- The face on every clip matches the persona image.
- The voice matches the uploaded sample.
- The hook/structure echoes the YouTube reference without verbatim copy.
- The color/light matches the style brief Claude wrote.
- The user could have edited the script in the UI before generation.

All tests pass. Service restart loads the new code.
