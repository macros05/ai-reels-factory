# ai-reels-factory

Studio end-to-end para producir reels hiperrealistas dirigidos por **Claude** y renderizados por **Higgsfield**. Le pasas un brief rico (tema · audiencia · tono · mood · vibra visual · referencias · character) y obtienes:

- `video.mp4` — vertical 1080×1920, 20-30s, voz sincronizada (o solo música) y subtítulos quemados opcionales
- `caption.txt` — copy + hashtags
- `script.json` — guion editable (hook · body · cta · caption · hashtags · visual_prompts)
- `result.json` — incluye el **shot plan** frame-by-frame del director (shot size, lente, cámara, luz, beats temporales, paleta y prompt final por clip)
- `audio.mp3`, `subtitles.srt`, `clips/clip_XX.mp4` — artefactos intermedios reutilizables

Dos formas de orquestar — equivalentes y complementarias:

1. **Interfaz web** — formulario con brief estructurado (chips de tono/mood/vibra, paleta, CTA, notas, voiceless, keyframes con Nano-Banana-Pro, Soul-ID, referencias), editor del guion y editor del **shot plan frame-by-frame**: hand-edit de cada campo, "Pedir al director" en lenguaje natural sobre un shot concreto, regeneración de un único clip y re-ensamblado del MP4 sin tocar Claude/ElevenLabs.
2. **MCP server** (`reels-mcp`) — Claude Desktop / Claude Code / cualquier cliente MCP conduce el pipeline con tools tipadas: `create_reel`, `get_shot_plan`, `refine_shot`, `update_shot`, `replace_shot_plan`, `update_script`, `confirm_run`, `regenerate_clip`, `reassemble`, `add_reference`, `set_brief`, `wait_until_status`, etc. **La misma cobertura que la interfaz**, controlable desde el chat.

## Flujo

```
brief (UI / MCP)
  └── script_generator   ← Claude: hook · body · cta · caption · hashtags · prompts borrador
        └── style_extractor   ← Claude vision: 60-word brief de paleta/óptica/mood a partir de refs
              └── director           ← Claude: shot plan frame-by-frame (shot size · lente · cámara · luz · beats · prompt final)
                    └── voice_generator    ← ElevenLabs (omitido si voiceless o Veo)
                          └── video_generator    ← Higgsfield CLI: clips usando shot.final_prompt
                                └── subtitle_generator ← whisper-timestamped (opcional)
                                      └── assembler   ← ffmpeg: concat · audio · music bed · subs · loudnorm
```

El director es el añadido clave de v0.3: convierte el guion + las referencias + el brief estructurado en un plan de rodaje con cinematografía concreta por clip. El video_generator prefiere `shot.final_prompt` y cae al `visual_prompts` del script si el director falla. La UI y el MCP exponen el plan para revisión y edición manual o asistida por Claude.

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje backend | Python 3.12 + FastAPI |
| Frontend | React 19 + Vite + TypeScript estricto + Tailwind v4 + TanStack Query + React Router v7 + framer-motion + Sonner |
| Auth | JWT HS256 (7 días) + password único, rate-limit en login (5 intentos / 15 min por IP) |
| Gestor de deps | [`uv`](https://docs.astral.sh/uv/) (backend) · npm (frontend) |
| Guion / copy | Anthropic `claude-sonnet-4-5` |
| Voz | ElevenLabs `eleven_v3` (omitida si `VIDEO_PROVIDER=veo`, que trae audio nativo) |
| Vídeo | **Seleccionable** vía `VIDEO_PROVIDER`: Veo 3.1, Kling 3.0 o Seedance 2.0 — todo vía **Higgsfield CLI** (auth navegador, sin API key) |
| Lip-sync | **Fusionado** dentro de la generación de vídeo: el audio de ElevenLabs se trocea por clip y se inyecta como `--audio` en Kling/Seedance. Veo lo trae nativo. Cero llamadas extra. |
| Characters | **Higgsfield Soul ID** entrenado con 5-20 fotos del rostro; reutilizable entre reels para mantener la misma cara entre clips (resuelve el "Kling pone una cara distinta en cada clip"). |
| Subtítulos | `whisper-timestamped` (local) |
| Ensamblado | `ffmpeg-python` |
| Logging | `loguru` |
| Config | `pydantic-settings` |

## MCP — Claude conduce el pipeline

`reels-mcp` es un servidor MCP (stdio) que expone el mismo backend al que llama
la UI. Una vez configurado, dile a Claude cosas como _"crea un reel sobre el
ritual del café especialidad con mood intimista y paleta cálida; cuando esté el
shot plan, refina el shot 2 para que sea wide al amanecer y regenera ese clip"_
y Claude maneja la orquestación entera.

Añade esto a `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) o equivalente:

```json
{
  "mcpServers": {
    "ai-reels-factory": {
      "command": "uv",
      "args": ["run", "reels-mcp"],
      "cwd": "/ruta/absoluta/a/ai-reels-factory"
    }
  }
}
```

Tools disponibles (resumen):

| Tool | Qué hace |
|---|---|
| `create_reel` | Arranca un reel con brief estructurado (audience, tone, mood, visual_vibe, palette, cta_goal, extra_notes), Soul-ID, voiceless, keyframes |
| `get_run` · `list_runs` · `wait_until_status` | Estado del pipeline, polling, terminales |
| `get_script` · `update_script` | Lee y reescribe el guion sin volver a llamar a Claude |
| `confirm_run` | Reanuda un run en `script_ready` con el guion editado |
| `get_shot_plan` · `replace_shot_plan` · `update_shot` · `refine_shot` | Plan frame-by-frame: lee, sobreescribe, parchea un campo, o pídele a Claude que reescriba un shot desde una instrucción en lenguaje natural |
| `regenerate_clip` · `reassemble` | Re-renderiza un clip individual (sólo paga el provider de vídeo de ese clip) y re-ensambla el MP4 final reusando el resto de artefactos |
| `add_reference` · `list_references` | Adjunta archivos (persona, style, script, voice, music) al run |
| `get_brief` · `set_brief` | Lee/parchea el brief estructurado |
| `get_final_video_path` · `providers_info` | Rutas, proveedores disponibles |

Ejemplo de prompt a Claude para una sesión típica:

> "Genera un reel sobre cómo dormir mejor sin pastillas. Audiencia: founders 25-40
> hispanohablantes. Tono íntimo, calmado. Mood cinematográfico, premium. Vibra:
> luz dorada, shallow DOF, handheld. Cuando llegue a `script_ready` enséñame el
> guion. Si el CTA me convence confírmalo. Cuando esté el shot plan, dame los 5
> shots resumidos. Si el shot 0 no me cuadra te pido que lo refines."

## Estructura

```
ai-reels-factory/
├── pyproject.toml
├── .env.example
├── src/                            ← backend Python
│   ├── config.py                   Settings desde .env (incl. APP_PASSWORD, JWT_SECRET)
│   ├── pipeline.py                 Orquestador con retry (tenacity, 3 intentos)
│   ├── models.py                   Modelos pydantic
│   ├── steps/
│   │   ├── script_generator.py     Claude → guion + caption + prompts
│   │   ├── voice_generator.py      ElevenLabs → audio.mp3 (omitido en Veo)
│   │   ├── video_generator.py      Higgsfield CLI · Veo/Kling/Seedance · lip-sync fused vía --audio · Soul-ID i2v
│   │   ├── subtitle_generator.py   whisper-timestamped → SRT
│   │   └── assembler.py            ffmpeg: concat + audio + subs quemados
│   ├── clients/
│   │   └── higgsfield.py           Wrapper subprocess de la CLI oficial `higgsfield`
│   ├── utils/
│   │   └── characters_db.py        SQLite local con los Soul-IDs entrenados
│   └── api/
│       ├── auth.py                 JWT + login + dependency
│       ├── characters.py           Endpoints Soul-ID (entrenar, listar, borrar)
│       └── main.py                 Routers /api/* + SPA static mount
├── frontend/                       ← React 19 + Vite + Tailwind v4
│   ├── package.json
│   ├── vite.config.ts              proxy /api → :8000 en dev
│   └── src/
│       ├── App.tsx / routes.tsx    QueryClient + BrowserRouter + Sonner
│       ├── pages/                  LoginPage, HomePage, ReelDetailPage
│       ├── components/
│       │   ├── ui/                 Button, Input, Textarea, Card, Badge, Skeleton, Dialog
│       │   ├── layout/             Header, ProtectedRoute
│       │   ├── auth/               LoginForm
│       │   ├── runs/               RunForm, ProviderSelect, GalleryGrid, ReelCard, ReelPlayer
│       │   └── reel-detail/        ReelDetailView, CaptionEditor, HashtagChips
│       ├── hooks/                  useAuth, useRuns, useRun, useCreateRun, useProviders
│       └── lib/                    api.ts, auth.ts, utils.ts
└── tests/
    ├── test_pipeline.py            mocks de todas las APIs externas
    └── test_auth.py                JWT, rate limit, /api/* protección
```

## Instalación

Requiere Python 3.12, Node 18+, `ffmpeg` instalado en el sistema y [`uv`](https://docs.astral.sh/uv/#installation).

```bash
# 1. instalar uv (si no lo tienes)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. clonar e instalar deps Python
git clone <repo>
cd ai-reels-factory
uv sync --extra dev

# 3. instalar la CLI oficial de Higgsfield (una sola vez por host)
sudo npm install -g @higgsfield/cli
higgsfield auth login   # abre el navegador, autoriza con tu cuenta

# 4. configurar variables
cp .env.example .env
# editar .env con las claves de Anthropic + ElevenLabs
```

### Variables de entorno

```env
ANTHROPIC_API_KEY=sk-ant-…
ELEVENLABS_API_KEY=…
ELEVENLABS_VOICE_ID=…        # el ID de la voz que quieres usar
VIDEO_PROVIDER=seedance      # uno de: seedance | kling | veo

# Higgsfield NO necesita API key — se autentica vía CLI (paso 3 de arriba).
# Si el binario no está en $PATH, descomenta:
# HF_CLI_PATH=/usr/local/bin/higgsfield

APP_PASSWORD=tu-password     # password único de acceso a la app
JWT_SECRET=…                 # genera con: openssl rand -hex 32
```

### Cómo elegir proveedor

| Proveedor   | Audio                            | Lip-sync                                 | Soul-ID | Coste aprox |
|-------------|----------------------------------|-------------------------------------------|---------|-------------|
| `seedance`  | ElevenLabs (eleven_v3)           | Fused vía `--audio` en la misma llamada   | Sí      | ~50 cr/reel |
| `kling`     | ElevenLabs (eleven_v3)           | Fused vía `--audio` en la misma llamada   | Sí      | ~250 cr/reel|
| `veo`       | Nativo (Veo lo genera)           | Nativo                                    | No      | ~1200 cr/reel|

Resumen rápido:
- **¿Quieres mantener tu voz clonada en castellano?** Usa `seedance` o `kling`.
- **¿Quieres usar SÓLO Higgsfield, sin ElevenLabs?** Usa `veo`.
- **¿Quieres misma cara en todos los reels?** Entrena un Character (Soul ID) y selecciónalo al lanzar — funciona en `seedance` y `kling`.

## Uso

### Producción (un solo proceso)

Build el frontend una vez y arranca uvicorn — FastAPI sirve la SPA buildeada en `/` y el API en `/api/*`:

```bash
cd frontend && npm install && npm run build && cd ..
uv run uvicorn src.api.main:app --port 8000
```

Abre <http://localhost:8000>. Te redirige a `/login` si no tienes sesión.

### Desarrollo (dos procesos)

```bash
# Terminal 1: backend
uv run uvicorn src.api.main:app --port 8000 --reload

# Terminal 2: frontend (HMR)
cd frontend && npm run dev    # → http://localhost:5173
```

Vite proxea `/api/*` al backend, así que abres siempre `http://localhost:5173`.

### Frontend

- `npm run dev` — Vite con HMR, proxy `/api → :8000`
- `npm run build` — `tsc -b --noEmit && vite build` → `frontend/dist/`
- `npm run preview` — sirve `dist/` con Vite preview
- `npm run typecheck` — solo TypeScript estricto

### Autenticación

- **Password único** definido en `APP_PASSWORD`. Se compara con `hmac.compare_digest` (constant-time).
- **JWT HS256** firmado con `JWT_SECRET`, expira a los 7 días. Genera el secreto con `openssl rand -hex 32`.
- **Sesión** persiste en `localStorage` (`reels.token`); el frontend la usa vía `Authorization: Bearer …` o, para `<video src>`, vía `?token=…` en la query.
- **Rate limit**: `POST /api/auth/login` admite 5 intentos / 15 min por IP (slowapi → 429).
- **Logout** desde el botón del header o automático si la API devuelve 401 (token caducado o `JWT_SECRET` rotado).

Para cambiar la contraseña: edita `APP_PASSWORD` en `.env` y reinicia uvicorn. Para invalidar todas las sesiones existentes: rota `JWT_SECRET`.

### Characters (Soul ID)

Higgsfield Soul ID es un mini-entrenamiento de cara: subes 5-20 fotos del rostro y obtienes un `soul_id` reutilizable que fija la misma cara entre reels. Es lo que Kling 2.6 text-to-video nunca podía garantizar (cada clip salía con cara distinta).

**Para crear un character desde la app:**
1. En la home, pestaña **Characters** → "Nuevo character".
2. Nombre + modelo (`Soul 2.0` para uso general; `Soul Cinematic` para look fotográfico).
3. Arrastra 5-20 fotos del rostro (jpg/png/webp). Distintos ángulos y expresiones; sin gafas de sol ni cara recortada.
4. Pulsa **Entrenar**. Higgsfield tarda 3-5 min; el badge pasa de `training` → `ready` solo (la lista se autoactualiza cada 5s).

**Para usar un character en un reel:** en la home, pestaña **Crear** → desplegable "Character (Soul ID)" → selecciona uno `ready`. El pipeline:
1. Genera un still por clip con `text2image_soul_v2 --soul-id <id> --prompt <visual_prompt>` → misma cara, escenas distintas.
2. Pasa cada still como `--start-image` a Kling/Seedance, junto al segmento de audio de ElevenLabs → vídeo lip-synced.

Veo3.1 no soporta Soul ID (la generación se hace text-to-video con audio nativo, sin slot para Soul). Si seleccionas Veo + Character, el frontend desactiva el selector.

**Costes:** el entrenamiento (`soul-id create`) consume ~100 créditos una sola vez. Después cada reel paga el coste del proveedor + ~5 cr por still extra por clip.

### Vía API (sin frontend)

```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"password":"tu-password"}' | jq -r .token)

# 2. Lanzar run
curl -X POST http://localhost:8000/api/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"topic":"cómo dormir mejor sin pastillas"}'
# → {"run_id": "20260515-143205", "status": "pending"}
```

Mientras corre, el output va apareciendo en `./output/{run_id}/`:

```
output/20260515-143205/
├── audio.mp3
├── clips/clip_00.mp4 … clip_04.mp4
├── concat.mp4
├── subtitles.srt
├── script.json
├── caption.txt
├── video.mp4         ← entregable final
└── result.json       ← estado y metadatos del run
```

### Tests

```bash
uv run pytest                # backend: pipeline + auth (31 tests)
cd frontend && npm run build # frontend: TS estricto + bundle
```

Los tests del backend usan mocks — no se llaman APIs externas ni se ejecuta ffmpeg.

## Coste estimado por reel

Tarifas vigentes a 2026-05 (orientativas, contrastar con dashboards de cada proveedor). Claude y Whisper son fijos:

- Guion (~1k tokens out) — Anthropic Sonnet 4.5: ~$0.015
- Subtítulos — Whisper local: $0
- Ensamblado — ffmpeg local: $0
- Voz (~60 palabras / ~25s) — ElevenLabs `eleven_v3`: ~$0.07 (no se cobra si el proveedor de vídeo trae audio nativo)
- Lip-sync (25s a $3/min) — Sync Labs Lipsync 2 (`fal-ai/sync-lipsync/v2`) en fal.ai: ~$1.25 (solo en Kling/Seedance; Veo trae lip-sync nativo)

### Por proveedor de vídeo

| Proveedor | Modelo fal.ai | Clips | Duración total | Coste vídeo | Voz + lip-sync | **Total / reel** |
|---|---|---|---|---|---|---|
| **Seedance + Sync Lipsync** | `fal-ai/bytedance/seedance/v1/lite/text-to-video` | 5 × 5s | 25s | ~$0.55 (5 × $0.11) | ElevenLabs + ~$1.25 Sync Lipsync | **~$1.90** |
| **Kling + Sync Lipsync** | `fal-ai/kling-video/v2.6/pro/text-to-video` | 5 × 5s | 25s | ~$1.75 (5 × $0.35) | ElevenLabs + ~$1.25 Sync Lipsync | **~$3.10** |
| **Veo 3.1** (audio + lip-sync nativos, sin Sync Lipsync) | `fal-ai/veo3` | 3 × 8s | 24s | ~$12 (3 × $4, ~$0.50/seg) | nativa | **~$12** |

### Cómo elegir proveedor

- **Seedance + Sync Lipsync** — máximo volumen, calidad aceptable, ideal para iterar topics rápido sin disparar el presupuesto. Es el setup por defecto.
- **Kling + Sync Lipsync** — calidad/precio óptimo para producción regular. Mejor coherencia temporal y movimiento de cámara que Seedance, lip-sync limpio gracias a Sync Labs; sigue siendo asequible para piezas semanales.
- **Veo 3.1** — pieza hero, presentación a cliente, contenido premium. Calidad top, audio diegético y lip-sync nativos; cambia la economía (un reel cuesta ~4× lo que Kling+Sync), reserva para cuando la pieza tiene que sobresalir.

> Al cambiar `VIDEO_PROVIDER` el pipeline ajusta automáticamente: número de clips (3 para Veo, 5 para los otros), prompts pedidos a Claude y, en el caso de Veo, se saltan ElevenLabs y el lip-sync de Sync Labs — los subtítulos se transcriben del audio embebido en los propios clips.

## Decisiones de diseño

- **uv** en lugar de pip/poetry: resolución y locking más rápidos, gestiona venvs automáticamente.
- **Dispatcher por env var**: `VIDEO_PROVIDER` selecciona el modelo en `src/steps/video_generator.py`. Validado por pydantic — un valor inválido revienta al arrancar con error claro. Sin flags de retrocompatibilidad.
- **Clips en paralelo**: independientemente del proveedor, los clips se piden a fal.ai con `asyncio.gather` para minimizar latencia total (~1-2 min en vez de ~5-10). El lip-sync de Sync Labs también corre los 5 clips en paralelo.
- **Veo skip voice + lip-sync**: si `VIDEO_PROVIDER=veo`, el pipeline marca `skip_voice_generation=True` y `skip_lipsync=True` y se salta ElevenLabs y Sync Lipsync. Los clips de Veo traen audio nativo (incluido lip-sync) y `subtitle_generator` concatena los audios de los clips (no solo el primero — única forma de cubrir los 24s completos con subtítulos) antes de pasarlos a Whisper.
- **Lip-sync con Sync Labs Lipsync 2** (solo Kling/Seedance): después de generar los clips y el audio de ElevenLabs, recortamos el audio en ventanas correspondientes a cada clip (`clip N → [N·5s, (N+1)·5s)`) y mandamos cada par (vídeo, audio) a `fal-ai/sync-lipsync/v2` en paralelo. Los clips resincronizados sobreescriben `context["video_clips"]`; los originales quedan en `clips/` y en `context["video_clips_pre_lipsync"]` para debug. El plan original mencionaba Hedra Character-3 pero ese modelo no está deployado en fal.ai — Sync Labs es el lipsync de referencia disponible.
- **Coherencia visual**: el `persona_description` se exige al modelo de guion y se reutiliza en cada `visual_prompt`. No es 100% determinista (ninguno de los 3 proveedores ofrece character lock en text-to-video), pero baja la varianza notablemente.
- **Subtítulos quemados con whisper-timestamped**: transcribimos el audio real (sea ElevenLabs o el embebido por Veo) en vez del guion original, así los timings encajan perfectamente con la voz.
- **Retry con tenacity** (3 intentos, backoff exponencial 1-10s) por step. Las APIs externas son ruidosas; un fallo transitorio no debe tirar el run completo.
- **Estado de runs en disco** (`result.json` por run): no usamos base de datos. El dashboard reconstruye el estado leyendo `./output/`.
- **HTMX** para el dashboard: cero build, polling cada 5s, suficiente para una herramienta interna.

## Limitaciones conocidas

- No hay autenticación en el dashboard — pensado para uso local.
- No hay cola de jobs; los runs corren en `BackgroundTasks` de FastAPI. Para producción seria, mete Redis + RQ o Celery.
- La consistencia de la persona entre clips es "best effort" basada en prompts. Para character lock real necesitarías image-to-video con un keyframe fijo (no soportado aún en este pipeline).
- `whisper-timestamped` carga el modelo `base` la primera vez; el primer run es más lento (~30s de carga del modelo).
- El proveedor se fija al arrancar el proceso (lee `.env` una vez). Cambiar de proveedor requiere reiniciar uvicorn.
