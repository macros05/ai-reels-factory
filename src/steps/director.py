"""Frame-by-frame director, powered by Claude.

This step bridges raw script → video generator. The script gives us the spoken
words and a generic visual prompt per clip; the director turns those into a
hyperdetailed shot plan: shot size, lens, lighting, camera move, action beats
on a per-second timeline, color palette, transitions and the fully-composed
final prompt the video model should receive.

Why split this from `script_generator`?

1. Concerns. The script step balances word-count, hooks and CTAs — adding 8
   cinematography fields to the same JSON inflates the prompt and degrades
   both outputs. Two focused calls beat one bloated call.
2. Iteration. With the plan as its own artifact, the operator (or a Claude
   running on MCP) can refine a single shot without re-rolling the script,
   and the video step can pick up the refined plan transparently.
3. Style absorption. The director sees the script + style_brief + persona
   + structured creative brief together; it can compose a single
   `final_prompt` per shot that's already tuned for Higgsfield's parser.

The video generator prefers `shot.final_prompt` when populated and falls back
to `script.visual_prompts[i]` otherwise — so this step is additive: if it
fails or is skipped, the pipeline keeps working with the legacy prompts.
"""

from __future__ import annotations

import json
from typing import Any

from anthropic import AsyncAnthropic
from loguru import logger

from src.config import VideoProvider, settings
from src.models import CreativeBrief, ScriptOutput, Shot, ShotPlan


_SYSTEM = """Eres un director de cine y publicidad senior. Tu trabajo es coger
un guion ya escrito y convertirlo en un PLAN DE RODAJE FRAME-BY-FRAME para que
un modelo de generación de vídeo (Veo / Kling / Seedance / Cinematic Studio)
produzca cada toma con dirección concreta — no prompts vagos.

Devuelves SIEMPRE un único objeto JSON estricto, sin texto adicional, sin
markdown, sin ```json.

Reglas duras:

0. COHERENCIA ENTRE CLIPS — antes de escribir nada, decide UN lenguaje de
   cámara base coherente para todo el reel (handheld, locked-off + dolly,
   orbit lento, etc.) y úsalo en TODOS los shots con variaciones SUTILES
   por shot. La pieza tiene que verse como un solo rodaje, no como 5
   estilos distintos pegados. Variar el `camera_move` está permitido pero
   debe sentirse parte del mismo lenguaje (p.ej. todo handheld pero con
   distancias y direcciones distintas). El campo top-level
   `camera_directive` recoge esa decisión en 1-2 frases.

1. Generas EXACTAMENTE {num_shots} shots, uno por cada clip de
   {clip_seconds} segundos. Índices 0…{last_index}.

2. Cada shot debe incluir TODOS estos campos, sin omitir ninguno:
   - index (int)
   - shot_size: uno de extreme_close_up | close_up | medium_close_up |
     medium | medium_wide | wide | extreme_wide
   - camera_move: descripción cinematográfica concreta en inglés
     coherente con `camera_directive` (e.g. "slow handheld push-in, 4°
     horizon shake", "handheld lateral drift right at waist height",
     "handheld subtle pull-back from CU to MS"). NUNCA "static" o
     "no movement" — siempre algo de vida.
   - lens_mm: 18 | 24 | 28 | 35 | 50 | 85 (entero)
   - aperture: e.g. "f/1.8", "f/2.8"
   - lighting: descripción concreta del esquema de iluminación
   - location: dónde transcurre la escena (1 línea, específico)
   - wardrobe: ropa exacta de la persona (consistente con persona_lock)
   - props: lista de objetos relevantes en escena (puede ir vacía)
   - action_beats: lista de 2-4 strings con beats temporales en formato
     "[Xs-Ys] descripción de la acción" cubriendo los {clip_seconds}s.
     Cada beat es lo que la persona HACE en esa ventana.
   - dialogue_excerpt: fragmento exacto del guion que se pronuncia en ese
     clip (puede ser vacío en clips silenciosos)
   - emotion: 2-4 palabras (e.g. "quiet, hopeful, intimate")
   - color_palette: 3-5 colores con valor descriptivo
     (e.g. "warm honey, deep navy, off-white, soft amber")
   - transition_in / transition_out: "hard cut" | "match cut" | "smash cut"
     | "whip pan" | "speed ramp" | "morph cut"
   - duration_seconds: número (= clip_seconds salvo Veo)
   - final_prompt: PROMPT FINAL EN INGLÉS, 50-90 palabras, listo para
     enviar al modelo de vídeo. Debe empezar con persona_lock (traducida
     a inglés), incluir shot_size + camera_move + lens + lighting +
     action beats resumidos + color palette + cola
     "hyperrealistic, 9:16, shot on Sony FX3, shallow depth of field,
     35mm equivalent, natural skin texture, ambient sound design".
     NUNCA empieces con "the scene" o "a video of"; empieza con la persona.

3. style_brief (top level): párrafo de 40-60 palabras en inglés cubriendo
   la estética global (paleta, óptica, mood, grano, contrast) — se anexa
   al final de cada prompt. Coherente con todos los shots.

4. persona_lock (top level): descripción VISUAL invariante de la persona
   protagonista (género, edad aparente, rasgos, peinado, color de pelo,
   ropa base). En INGLÉS. Esta descripción se reusa LITERAL en cada shot
   y blinda la consistencia entre clips.

5. logline (top level): 1 frase de máx 25 palabras que resume el reel
   como si fuese un poster (en español).

6. title (top level): título cinematográfico corto (3-7 palabras, español).

Esquema JSON exacto:
{{
  "title": str,
  "logline": str,
  "style_brief": str,
  "persona_lock": str,
  "camera_directive": str,
  "shots": [
    {{
      "index": int,
      "shot_size": str,
      "camera_move": str,
      "lens_mm": int,
      "aperture": str,
      "lighting": str,
      "location": str,
      "wardrobe": str,
      "props": [str, ...],
      "action_beats": [str, ...],
      "dialogue_excerpt": str,
      "emotion": str,
      "color_palette": str,
      "transition_in": str,
      "transition_out": str,
      "duration_seconds": float,
      "final_prompt": str
    }} … {num_shots} elementos
  ]
}}"""


_USER_TEMPLATE = """TEMA / BRIEF:
{topic}

{brief_block}

GUION:
- Hook: {hook}
- Body: {body}
- CTA: {cta}
- Full script: {full_script}

PERSONA (visual description del script):
{persona_description}

PROMPTS VISUALES BORRADOR (referencia, mejóralos):
{draft_prompts}

ESTILO VISUAL (extraído de referencias del usuario, si hay):
{style_brief}

Construye el plan completo. Recuerda: {num_shots} shots, {clip_seconds}s cada
uno, EXACTAMENTE el JSON del esquema, nada más."""


def _build_user_prompt(
    *,
    topic: str,
    brief: CreativeBrief | None,
    script: ScriptOutput,
    style_brief: str,
    num_shots: int,
    clip_seconds: int,
) -> str:
    brief_block = ""
    if brief is not None:
        parts: list[str] = []
        if brief.audience:
            parts.append(f"- Audiencia objetivo: {brief.audience}")
        if brief.tone:
            parts.append(f"- Tono: {', '.join(brief.tone)}")
        if brief.mood:
            parts.append(f"- Mood: {', '.join(brief.mood)}")
        if brief.visual_vibe:
            parts.append(f"- Vibras visuales: {', '.join(brief.visual_vibe)}")
        if brief.palette:
            parts.append(f"- Paleta sugerida: {brief.palette}")
        if brief.cta_goal:
            parts.append(f"- Objetivo de CTA: {brief.cta_goal}")
        if brief.extra_notes:
            parts.append(f"- Notas extra: {brief.extra_notes}")
        if parts:
            brief_block = "CONTEXTO CREATIVO ADICIONAL:\n" + "\n".join(parts)

    draft = "\n".join(
        f"  [{i}] {p}" for i, p in enumerate(script.visual_prompts[:num_shots])
    ) or "  (vacío — el director debe inventar los planos coherentes con el guion)"

    return _USER_TEMPLATE.format(
        topic=topic,
        brief_block=brief_block,
        hook=script.hook,
        body=script.body,
        cta=script.cta,
        full_script=script.full_script,
        persona_description=script.persona_description,
        draft_prompts=draft,
        style_brief=style_brief or "(no se han adjuntado referencias de estilo)",
        num_shots=num_shots,
        clip_seconds=clip_seconds,
    )


class DirectorStep:
    """Builds a frame-by-frame ShotPlan from script + context with Claude."""

    name = "director"

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        self._client = client

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        script: ScriptOutput = context["script"]
        provider: VideoProvider = context.get("provider", settings.video_provider)
        num_shots = settings.clip_count_for(provider)
        clip_seconds = settings.clip_duration_for(provider)
        topic: str = context.get("topic", "")
        brief: CreativeBrief | None = context.get("brief")
        style_brief: str = context.get("style_brief", "") or ""

        system = _SYSTEM.format(
            num_shots=num_shots,
            clip_seconds=clip_seconds,
            last_index=num_shots - 1,
        )
        user = _build_user_prompt(
            topic=topic,
            brief=brief,
            script=script,
            style_brief=style_brief,
            num_shots=num_shots,
            clip_seconds=clip_seconds,
        )

        logger.info(
            f"[director] composing shot plan — provider={provider} "
            f"shots={num_shots}×{clip_seconds}s style_brief={'yes' if style_brief else 'no'} "
            f"brief={'yes' if brief else 'no'}"
        )

        try:
            client = self._get_client()
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            raw = "".join(
                block.text
                for block in message.content
                if getattr(block, "type", None) == "text"
            ).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
            data = json.loads(raw)
            shots_data = data.get("shots", [])
            if not isinstance(shots_data, list):
                raise ValueError("shots must be a list")
            shots = [Shot(**s) for s in shots_data][:num_shots]
            # Pad if Claude undershoots — clone the last shot to keep
            # downstream code simple (it only ever indexes up to num_shots).
            while len(shots) < num_shots:
                pad = shots[-1].model_copy(update={"index": len(shots)}) if shots else Shot(
                    index=len(shots),
                    duration_seconds=float(clip_seconds),
                    final_prompt=script.visual_prompts[len(shots) % max(1, len(script.visual_prompts))]
                    if script.visual_prompts
                    else script.persona_description,
                )
                shots.append(pad)

            plan = ShotPlan(
                title=str(data.get("title") or "").strip(),
                logline=str(data.get("logline") or "").strip(),
                style_brief=str(data.get("style_brief") or style_brief).strip(),
                persona_lock=str(data.get("persona_lock") or script.persona_description).strip(),
                camera_directive=str(data.get("camera_directive") or "").strip(),
                shots=shots,
            )

            # ── self-review pass ──
            # Claude audits its own plan for inconsistencies (camera
            # drifting, persona breaking, mismatched mood) and emits a
            # refined version. Capped at one extra call so cost stays
            # bounded. Soft-fails to the original plan on any error.
            plan = await self._self_review(plan)
        except Exception as exc:
            # Don't kill the run — fall back to a synthesized plan from the
            # script's visual_prompts so the video step still has something
            # to chew on. The plan won't be cinematic but the reel still ships.
            logger.warning(
                f"[director] failed ({type(exc).__name__}: {exc}); "
                f"falling back to script.visual_prompts"
            )
            plan = _fallback_plan(
                script=script,
                style_brief=style_brief,
                num_shots=num_shots,
                clip_seconds=clip_seconds,
            )

        logger.info(
            f"[director] plan ready — title={plan.title!r} shots={len(plan.shots)} "
            f"camera={plan.camera_directive!r}"
        )
        context["shot_plan"] = plan
        return context

    async def _self_review(self, plan: ShotPlan) -> ShotPlan:
        """Second pass: Claude audits the plan it just wrote.

        We give it the plan plus an explicit checklist (persona consistency,
        camera language coherence, prompt completeness) and ask for a
        revised JSON. The agent self-edits before the video step burns
        credits. One extra Claude call is dirt cheap compared to a wasted
        Higgsfield render.
        """
        try:
            client = self._get_client()
            review_system = (
                "Eres director de cine senior. Te paso un PLAN DE RODAJE en "
                "JSON que tú mismo acabas de escribir. Tu trabajo es auditarlo "
                "y devolver una VERSIÓN REVISADA en el MISMO esquema, sin "
                "texto ni markdown, sólo JSON.\n\n"
                "Checklist obligatorio:\n"
                "1. PERSONA: cada shot empieza con la misma persona descrita "
                "   en persona_lock — corrige si alguno deriva.\n"
                "2. CÁMARA: todos los camera_move pertenecen al mismo "
                "   lenguaje declarado en camera_directive. Variaciones "
                "   permitidas (distancia, dirección), pero NO cambios "
                "   radicales de registro (no mezclar handheld con orbit "
                "   cinematográfico salvo que camera_directive lo permita "
                "   explícitamente). Reescribe los que se salgan.\n"
                "3. PALETA: color_palette consistente en todos los shots, "
                "   con variaciones por escena pero no contradictorias.\n"
                "4. PROMPT FINAL: cada shot.final_prompt incluye persona + "
                "   shot_size + camera_move + lighting + beats resumidos + "
                "   color palette + cola técnica (hyperrealistic, 9:16, "
                "   shot on Sony FX3, shallow DOF). Reescríbelo si falta.\n"
                "5. CONTINUIDAD: si el wardrobe / props cambian entre shots, "
                "   justifica con un cambio de escena explícito en location.\n"
                "Si todo está bien, devuelve el plan tal cual. Si algo "
                "necesita arreglo, devuelve la versión corregida."
            )
            message = await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=review_system,
                messages=[
                    {
                        "role": "user",
                        "content": f"PLAN ACTUAL:\n{plan.model_dump_json(indent=2)}",
                    }
                ],
            )
            raw = "".join(
                b.text for b in message.content if getattr(b, "type", None) == "text"
            ).strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:].strip()
            data = json.loads(raw)
            revised = ShotPlan.model_validate(data)
            # Reject revisions that drop or add shots — we want a refinement,
            # not a re-plan. If the count doesn't match, keep the original.
            if len(revised.shots) != len(plan.shots):
                logger.warning(
                    f"[director] self-review changed shot count "
                    f"({len(plan.shots)} → {len(revised.shots)}); discarding"
                )
                return plan
            logger.info("[director] self-review pass applied")
            return revised
        except Exception as exc:
            logger.warning(
                f"[director] self-review skipped ({type(exc).__name__}: {exc})"
            )
            return plan


def _fallback_plan(
    *,
    script: ScriptOutput,
    style_brief: str,
    num_shots: int,
    clip_seconds: int,
) -> ShotPlan:
    prompts = list(script.visual_prompts[:num_shots])
    if len(prompts) < num_shots:
        last = prompts[-1] if prompts else script.persona_description
        prompts.extend([last] * (num_shots - len(prompts)))
    shots: list[Shot] = []
    for i, prompt in enumerate(prompts):
        shots.append(
            Shot(
                index=i,
                duration_seconds=float(clip_seconds),
                final_prompt=(
                    f"{prompt.rstrip('. ')}. {style_brief}".strip(". ") if style_brief else prompt
                ),
            )
        )
    return ShotPlan(
        title="",
        logline="",
        style_brief=style_brief,
        persona_lock=script.persona_description,
        shots=shots,
    )
