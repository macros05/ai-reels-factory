"""Script generation via Anthropic Claude."""

from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from src.config import VideoProvider, settings
from src.models import ScriptOutput

SYSTEM_PROMPT_TEMPLATE = """Eres un guionista experto en reels virales de Instagram en español.
Devuelves SIEMPRE un único objeto JSON estricto sin texto adicional, sin markdown, sin ```json.

Requisitos del guion:
- Hook contundente en los 2 primeros segundos (máx 12 palabras)
- Estructura: hook → desarrollo (body) → llamada a la acción (cta)
- Duración objetivo: {total_seconds} segundos hablados.
- LÍMITE DURO: full_script DEBE tener entre {word_min} y {word_max} palabras
  (cuenta cada palabra separada por espacio). NUNCA excedas {word_max} — si
  superas el límite el video corta el final. PRIORIZA SIEMPRE acabar el CTA
  sobre añadir detalles al body.
- Evita siglas que se pronuncien letra-a-letra (RRHH, IA, RGPD, etc.); escríbelas
  desarrolladas ("recursos humanos", "inteligencia artificial") o di la marca
  en su lugar. Esto es CRÍTICO para los subtítulos.
- Tono: directo, primera persona, casual, energético
- Idioma: español neutro (España, sin acento latino marcado)

Además generas:
- caption: copy para la publicación de Instagram (máx 200 caracteres, 1-2 frases con gancho)
- hashtags: array de 10-15 hashtags relevantes sin el símbolo # repetido
- persona_description: descripción VISUAL CONSISTENTE de la persona protagonista (género, edad,
  rasgos faciales, color y peinado de pelo, ropa concreta, escenario base con detalles de
  iluminación). Esta descripción se reutiliza IDÉNTICA en cada visual_prompt para mantener
  coherencia visual entre escenas. Sé muy específico.
- persona_gender: "female" o "male" — coherente con persona_description. CRÍTICO: la voz se
  elige a partir de este campo, así que tiene que coincidir con la persona que aparece.
- visual_prompts: array de EXACTAMENTE {num_clips} prompts visuales en inglés, uno por clip de
  {clip_seconds} segundos, cada uno empezando por la persona_description (traducida a inglés) y
  añadiendo:
  1) la acción concreta del tramo del guion (lo que la persona DICE Y HACE),
  2) MOVIMIENTO EXPLÍCITO de la persona: gesticula con las manos, asiente, gira, camina,
     señala, cambia de expresión. NUNCA estática.
  3) MOVIMIENTO DE CÁMARA distinto en cada clip: handheld push-in, dolly lateral, orbit,
     tilt up, follow-shot, rack focus. NUNCA cámara fija.
  4) Cola de estilo: hyperrealistic, cinematic, vertical 9:16, natural lighting, shallow
     depth of field, shot on Sony FX3, 35mm, 24fps.
  Cada prompt 40-70 palabras.

Esquema JSON exacto:
{{
  "hook": str,
  "body": str,
  "cta": str,
  "full_script": str,
  "caption": str,
  "hashtags": [str, ...],
  "persona_description": str,
  "persona_gender": "female" | "male",
  "visual_prompts": [{prompts_schema}]
}}
"""

USER_PROMPT_TEMPLATE = """Tema o trending topic: {topic}

Genera el guion completo siguiendo el sistema. Recuerda: solo JSON, nada más."""

REFERENCE_PROMPT_TEMPLATE = """Tema o trending topic: {topic}

REFERENCIAS DE GUION (úsalas como inspiración — toma el ÁNGULO, el HOOK y la
ESTRUCTURA, pero NO copies frases literales, no menciones a sus autores, y
asegúrate de que el guion final sigue siendo original y en línea con el tema):

{references}

Genera el guion completo siguiendo el sistema. Recuerda: solo JSON, nada más."""


def _build_system_prompt(provider: VideoProvider | None = None) -> str:
    p: VideoProvider = provider or settings.video_provider
    num_clips = settings.clip_count_for(p)
    clip_seconds = settings.clip_duration_for(p)
    total_seconds = num_clips * clip_seconds
    word_min, word_max = word_bounds_for(p)
    prompts_schema = ", ".join(["str"] * num_clips)
    return SYSTEM_PROMPT_TEMPLATE.format(
        total_seconds=total_seconds,
        word_min=word_min,
        word_max=word_max,
        num_clips=num_clips,
        clip_seconds=clip_seconds,
        prompts_schema=prompts_schema,
    )


def word_bounds_for(provider: VideoProvider) -> tuple[int, int]:
    """Return (word_min, word_max) for the script generator.

    Veo runs at a generous cap (30..100 words) because briefs frequently
    include a verbatim script and Claude must reproduce it without
    truncation. Kling/Seedance keep the tight ~2.2 words/sec cap because
    ElevenLabs reads the script and we want the audio to finish inside
    the 25s clip timeline.
    """
    if provider == "veo":
        return 30, 100
    total_seconds = settings.clip_count_for(provider) * settings.clip_duration_for(provider)
    return int(total_seconds * 1.6), int(total_seconds * 2.2)


class ScriptGeneratorStep:
    """Generates the reel script + caption + visual prompts using Claude."""

    name = "script_generator"

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        self._client = client

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        topic: str = context["topic"]
        provider: VideoProvider = context.get("provider", settings.video_provider)
        script_refs: list[Any] = [
            r for r in context.get("references", []) if r.kind == "script"
        ]
        logger.info(
            f"[script_generator] topic={topic!r} provider={provider} "
            f"script_refs={len(script_refs)}"
        )

        if script_refs:
            chunks: list[str] = []
            for i, ref in enumerate(script_refs, start=1):
                try:
                    text = ref.path.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    logger.warning(f"[script_generator] failed to read {ref.path}: {exc}")
                    continue
                header = f"--- Referencia {i}" + (f" ({ref.source_url})" if ref.source_url else "") + " ---"
                chunks.append(f"{header}\n{text}")
            user_content = REFERENCE_PROMPT_TEMPLATE.format(
                topic=topic, references="\n\n".join(chunks)
            )
        else:
            user_content = USER_PROMPT_TEMPLATE.format(topic=topic)

        client = self._get_client()
        message = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=_build_system_prompt(provider),
            messages=[{"role": "user", "content": user_content}],
        )

        raw = "".join(
            block.text for block in message.content if getattr(block, "type", None) == "text"
        ).strip()

        if raw.startswith("```"):
            raw = raw.strip("`")
            if raw.lower().startswith("json"):
                raw = raw[4:].strip()

        data = json.loads(raw)
        script = ScriptOutput(**data)
        word_count = len(script.full_script.split())
        _, word_max = word_bounds_for(provider)
        hard_cap = int(word_max * 1.5)
        if word_count > hard_cap:
            raise ValueError(
                f"script runaway: {word_count} words exceeds hard cap {hard_cap} "
                f"(soft target {word_max}). Retrying."
            )
        if word_count > word_max:
            logger.warning(
                f"[script_generator] script over target — {word_count} > {word_max} words; "
                f"voice_generator will speed up audio (atempo) to fit the video timeline"
            )
        else:
            logger.info(f"[script_generator] script ok — {word_count} words (max {word_max})")

        context["script"] = script
        return context
