import { useState } from "react";
import { Copy, Check, Terminal, Cable, Workflow, Sparkles } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { cn } from "@/lib/utils";

type Section = "flow" | "mcp" | "endpoints";

export function HelpPage() {
  const [section, setSection] = useState<Section>("flow");

  return (
    <div className="relative-layer flex min-h-screen flex-col">
      <Header />
      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        <header className="mb-10 flex flex-col gap-3">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-zinc-400">
            <Sparkles className="size-3 text-violet-300" />
            Documentación
          </div>
          <h1 className="text-balance text-4xl font-semibold tracking-tight text-zinc-50 sm:text-5xl">
            <span className="text-gradient">Cómo usar</span> Reels Factory
          </h1>
          <p className="max-w-2xl text-[15px] leading-relaxed text-zinc-400">
            Tres maneras de operar la herramienta: por la UI, por el MCP server
            (Claude Desktop/Code) o por la API HTTP directa.
          </p>
        </header>

        <nav className="mb-8 flex flex-wrap gap-1 border-b border-white/[0.06]">
          {[
            { id: "flow" as const, label: "Funcionamiento general", icon: Workflow },
            { id: "mcp" as const, label: "Conectar al MCP", icon: Cable },
            { id: "endpoints" as const, label: "API HTTP", icon: Terminal },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSection(t.id)}
              className={cn(
                "relative -mb-px flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-all",
                section === t.id
                  ? "border-violet-400 text-zinc-50"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              )}
            >
              <t.icon className="size-3.5" />
              {t.label}
            </button>
          ))}
        </nav>

        {section === "flow" && <FlowSection />}
        {section === "mcp" && <McpSection />}
        {section === "endpoints" && <EndpointsSection />}
      </main>
    </div>
  );
}

/* -------------------- Funcionamiento general -------------------- */

function FlowSection() {
  return (
    <div className="space-y-10">
      <Block title="1 · Brief + referencias">
        <p>
          Desde la pestaña <strong>Crear reel</strong> del Home introduces el
          tema y abres el <em>BriefBuilder</em> para añadir audiencia, tono,
          mood, paleta y CTA. Opcionalmente subes referencias (vídeo de
          inspiración, foto de persona, transcripción, audio de voz a clonar,
          tema musical).
        </p>
        <p>
          Toggles importantes: <strong>Voiceless</strong> deja el reel
          music-only sin voz IA, <strong>Nano-Banana keyframes</strong> genera
          un still por clip antes del vídeo para fijar composición.
        </p>
      </Block>

      <Block title="2 · Modo autónomo (por defecto)">
        <p>
          Al pulsar <strong>"Crear reel · Claude lo dirige"</strong> el pipeline
          se ejecuta entero sin pausas. La UI cambia a un{" "}
          <em>AutonomousProgress</em> que muestra el paso vivo:
        </p>
        <ol className="ml-5 list-decimal space-y-1.5 marker:text-violet-400">
          <li>Componiendo guion (Claude)</li>
          <li>Leyendo referencias (style brief, persona, voice IVC)</li>
          <li>Dirigiendo shot plan frame-by-frame (Claude + auto-review)</li>
          <li>Sintetizando voz (ElevenLabs · omitido si voiceless)</li>
          <li>Renderizando clips (Higgsfield · Veo/Kling/Seedance)</li>
          <li>Subtitulando (Whisper local)</li>
          <li>Ensamblando MP4 (ffmpeg)</li>
        </ol>
        <p>
          Cuando termina, el navegador navega a <code>/run/&#123;id&#125;</code>
          con el reel listo.
        </p>
      </Block>

      <Block title="3 · Modo experto (opt-in)">
        <p>
          Activa <strong>"Modo experto · editar guion a mano"</strong> y el
          pipeline se pausa tras el guion. Editas hook/body/cta/caption en el{" "}
          <em>ScriptEditor</em> y pulsas <strong>Confirmar</strong> para que
          siga.
        </p>
      </Block>

      <Block title="4 · Edición frame-by-frame">
        <p>
          Cada reel tiene su <em>Shot plan</em> editable en{" "}
          <code>/run/&#123;id&#125;</code> → pestaña <strong>Shot plan</strong>.
        </p>
        <ul className="ml-5 list-disc space-y-1.5 marker:text-violet-400">
          <li>
            Editas a mano cualquier campo de un Shot (lente, apertura,
            iluminación, paleta, action beats, prompt final…).
          </li>
          <li>
            <strong>"Pedir al director"</strong>: reescribes un Shot en lenguaje
            natural y Claude lo recompone.
          </li>
          <li>
            <strong>"Regenerar este clip"</strong>: solo gasta el render de
            Higgsfield, no Claude ni ElevenLabs.
          </li>
          <li>
            <strong>"Re-ensamblar vídeo"</strong>: rehace el MP4 final con los
            clips actuales, sin tocar providers.
          </li>
        </ul>
      </Block>

      <Block title="5 · Outputs">
        <p>
          Cada run guarda en <code>output/&#123;run_id&#125;/</code>:
        </p>
        <ul className="ml-5 list-disc space-y-1 marker:text-violet-400">
          <li><code>video.mp4</code> — el reel final 1080×1920</li>
          <li><code>caption.txt</code> — copy + hashtags</li>
          <li><code>script.json</code> — guion + shot plan</li>
          <li><code>audio.mp3</code>, <code>subtitles.srt</code>, <code>clips/clip_XX.mp4</code> — artefactos</li>
        </ul>
      </Block>
    </div>
  );
}

/* -------------------- Conectar al MCP -------------------- */

function McpSection() {
  return (
    <div className="space-y-10">
      <Block title="¿Qué es el MCP server?">
        <p>
          <code>reels-mcp</code> expone el pipeline al Model Context Protocol.
          Cualquier cliente compatible (Claude Desktop, Claude.ai web, Claude
          Code, Cursor) puede orquestar reels end-to-end sin pasar por HTTP:
          pedirle a Claude "crea un reel sobre X, edita el Shot 3 para que sea
          handheld, regenera ese clip" funciona como una conversación normal.
        </p>
        <p>
          Hay <strong>dos modos de conectar</strong>: <em>stdio</em> (proceso
          local, solo si tienes el repo clonado) o <em>Streamable HTTP</em>{" "}
          (URL pública, funciona desde Claude.ai web).
        </p>
      </Block>

      <Block title="Modo A · Claude.ai web (conector HTTP)">
        <p>
          El conector personalizado de Claude.ai <strong>no permite añadir
          cabeceras custom</strong> (solo OAuth, que no implementamos). Por
          eso aceptamos el token también <strong>embebido en la URL</strong>,
          como path-segment. Igual de seguro porque HTTPS encripta toda la
          ruta en tránsito.
        </p>
        <p>
          En <code>claude.ai</code> → <strong>Configuración</strong> →{" "}
          <strong>Conectores</strong> → <strong>Añadir conector personalizado</strong>:
        </p>
        <ul className="ml-5 list-disc space-y-1.5 marker:text-violet-400">
          <li>
            <strong>Nombre</strong>: el que quieras (p. ej.{" "}
            <em>CreacionVideoMarcos</em>)
          </li>
          <li>
            <strong>URL del servidor</strong>:{" "}
            <code>
              https://reels.marcosmorales.dev/mcp/&lt;MCP_TOKEN&gt;/
            </code>
            <br />
            La barra final es importante. Sustituye <code>&lt;MCP_TOKEN&gt;</code>{" "}
            por el valor que tienes en{" "}
            <code>/opt/ai-reels-factory/.env</code>.
          </li>
          <li>
            <strong>OAuth Client ID / Secret</strong>: déjalos en blanco.
          </li>
        </ul>
        <p>
          Tres capas protegen el endpoint para que nadie te queme créditos:
        </p>
        <ol className="ml-5 list-decimal space-y-1.5 marker:text-violet-400">
          <li>
            <strong>Token MCP</strong> de 32 bytes aleatorios — sin él la
            request se rechaza con 401 (acepta también como header{" "}
            <code>Authorization: Bearer …</code>).
          </li>
          <li>
            <strong>Whitelist de IPs</strong> con{" "}
            <code>MCP_ALLOWED_IPS</code> en <code>.env</code> (recuerda que
            tu IP pública vista por el server es la de tu router; si tu ISP
            te asigna IP dinámica tendrás que actualizarla).
          </li>
          <li>
            <strong>Rate limit</strong> por IP: 30 peticiones/minuto, ajustable
            con <code>MCP_RATE_LIMIT_PER_MINUTE</code>.
          </li>
        </ol>
        <p className="text-[12.5px] text-zinc-500">
          Rotar la clave: edita <code>MCP_TOKEN</code> en <code>.env</code> y{" "}
          <code>systemctl restart reels-factory</code>. La URL con el token
          viejo deja de funcionar inmediatamente.
        </p>
      </Block>

      <Block title="Modo B · Claude Desktop (proceso local stdio)">
        <p>
          Solo si el repo está clonado en la máquina donde corre Claude
          Desktop. Edita <code>~/Library/Application Support/Claude/claude_desktop_config.json</code>{" "}
          (macOS) o <code>%APPDATA%\Claude\claude_desktop_config.json</code>{" "}
          (Windows):
        </p>
        <CodeBlock
          lang="json"
          code={`{
  "mcpServers": {
    "reels-factory": {
      "command": "uv",
      "args": [
        "--directory", "/opt/ai-reels-factory",
        "run", "reels-mcp"
      ]
    }
  }
}`}
        />
        <p>
          Reinicia Claude Desktop. En el menú de la conversación verás{" "}
          <em>reels-factory</em> en la lista de servidores activos.
        </p>
      </Block>

      <Block title="Modo C · Claude Code (terminal)">
        <p>HTTP remoto (recomendado):</p>
        <CodeBlock
          lang="bash"
          code={`claude mcp add --transport http reels-factory https://reels.marcosmorales.dev/mcp/ \\
  --header "Authorization: Bearer $MCP_TOKEN"`}
        />
        <p>O stdio local:</p>
        <CodeBlock
          lang="bash"
          code={`claude mcp add reels-factory uv --directory /opt/ai-reels-factory run reels-mcp`}
        />
      </Block>

      <Block title="Herramientas disponibles (18)">
        <div className="grid gap-2 sm:grid-cols-2">
          {[
            ["list_runs", "Lista runs con estado y progreso"],
            ["create_reel", "Lanza un reel nuevo desde prompt + brief"],
            ["get_run", "Detalle de un run (estado, paths, scripts)"],
            ["get_script", "Solo el guion del run"],
            ["get_shot_plan", "Solo el shot plan estructurado"],
            ["update_shot", "Edita un Shot por índice"],
            ["refine_shot", "Reescribe un Shot vía instrucción NL"],
            ["replace_shot_plan", "Reemplaza el plan entero"],
            ["update_script", "Edita hook/body/cta/caption"],
            ["confirm_run", "Reanuda un run pausado en script-ready"],
            ["regenerate_clip", "Re-render solo de un clip"],
            ["reassemble", "Rehace video.mp4 sin tocar providers"],
            ["wait_until_status", "Bloquea hasta done/failed"],
            ["providers_info", "Estado Higgsfield, créditos, plan"],
            ["get_final_video_path", "Ruta absoluta del MP4 final"],
            ["get_brief", "Devuelve el CreativeBrief"],
            ["set_brief", "Reescribe el brief"],
            ["add_reference", "Añade ref (persona/style/script/voice/music)"],
            ["list_references", "Lista refs subidas al run"],
          ].map(([name, desc]) => (
            <div
              key={name}
              className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3"
            >
              <code className="text-[12px] font-semibold text-violet-300">
                {name}
              </code>
              <p className="mt-0.5 text-[12px] leading-snug text-zinc-400">
                {desc}
              </p>
            </div>
          ))}
        </div>
      </Block>

      <Block title="Ejemplo de conversación">
        <CodeBlock
          lang="text"
          code={`Tú:    Crea un reel sobre cómo el café de especialidad cambia
       el desayuno. Tono cálido, audiencia 25-35, mood pausado.
Claude: [usa create_reel → wait_until_status]
        Listo. Run abc123. ¿Quieres ver el shot plan?
Tú:    Sí, y el Shot 2 hazlo handheld con luz contraluz.
Claude: [usa get_shot_plan → refine_shot(2, ...)]
        Hecho. ¿Regenero solo ese clip?
Tú:    Sí.
Claude: [usa regenerate_clip(2) → reassemble]
        Renderizado. Path: /opt/ai-reels-factory/output/abc123/video.mp4`}
        />
      </Block>
    </div>
  );
}

/* -------------------- API HTTP -------------------- */

function EndpointsSection() {
  return (
    <div className="space-y-10">
      <Block title="Auth">
        <CodeBlock
          lang="bash"
          code={`curl -X POST http://127.0.0.1:8003/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"password":"tu_password"}'
# → { "token": "eyJ..." }  (JWT HS256, 7 días)`}
        />
        <p>
          Usa el token como <code>Authorization: Bearer …</code> en todas las
          rutas <code>/api/*</code>.
        </p>
      </Block>

      <Block title="Endpoints principales">
        <ul className="space-y-1.5 text-[13px] font-mono">
          <li><Method m="POST" /> <code>/api/run</code> · lanza un run autónomo</li>
          <li><Method m="POST" /> <code>/api/run/draft</code> · genera solo el guion (pausa en script-ready)</li>
          <li><Method m="POST" /> <code>/api/run/&#123;id&#125;/confirm</code> · reanuda tras editar guion</li>
          <li><Method m="GET" /> <code>/api/runs</code> · lista todos</li>
          <li><Method m="GET" /> <code>/api/runs/&#123;id&#125;</code> · detalle</li>
          <li><Method m="PUT" /> <code>/api/runs/&#123;id&#125;/shot-plan</code> · reemplaza shot plan</li>
          <li><Method m="POST" /> <code>/api/runs/&#123;id&#125;/shot-plan/refine</code> · refina un Shot vía NL</li>
          <li><Method m="POST" /> <code>/api/runs/&#123;id&#125;/clips/&#123;i&#125;/regenerate</code> · re-render de un clip</li>
          <li><Method m="POST" /> <code>/api/runs/&#123;id&#125;/reassemble</code> · rehace MP4 sin providers</li>
          <li><Method m="POST" /> <code>/api/references</code> · subir ref (persona/style/script/voice/music)</li>
          <li><Method m="GET" /> <code>/api/providers</code> · lista de providers y costes</li>
          <li><Method m="GET" /> <code>/api/higgsfield/status</code> · auth + créditos restantes</li>
        </ul>
        <p className="text-[12px] text-zinc-500">
          OpenAPI completo en <code>http://127.0.0.1:8003/openapi.json</code>.
        </p>
      </Block>

      <Block title="Ejemplo: crear un reel">
        <CodeBlock
          lang="bash"
          code={`TOKEN="…"
curl -X POST http://127.0.0.1:8003/api/run \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "topic": "cómo dormir mejor sin pastillas",
    "brief": {
      "audience": "25-40, vida agitada",
      "tone": ["cálido","didáctico"],
      "mood": ["pausado","íntimo"],
      "visual_vibe": ["wabi-sabi","golden hour"],
      "palette": "earthy beige + verde profundo",
      "cta_goal": "guardar el reel",
      "extra_notes": "minuto y treinta segundos"
    },
    "voiceless": false,
    "use_keyframes": true
  }'`}
        />
      </Block>
    </div>
  );
}

/* -------------------- helpers -------------------- */

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/[0.06] bg-white/[0.02] p-6 backdrop-blur-sm sm:p-8">
      <h2 className="mb-4 text-lg font-semibold tracking-tight text-zinc-100">
        {title}
      </h2>
      <div className="space-y-3 text-[14px] leading-relaxed text-zinc-400 [&_code]:rounded [&_code]:bg-white/[0.06] [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[12.5px] [&_code]:text-zinc-200 [&_strong]:font-semibold [&_strong]:text-zinc-100">
        {children}
      </div>
    </section>
  );
}

function Method({ m }: { m: string }) {
  const tone = {
    GET: "text-cyan-300 border-cyan-500/30 bg-cyan-500/10",
    POST: "text-violet-300 border-violet-500/30 bg-violet-500/10",
    PUT: "text-amber-300 border-amber-500/30 bg-amber-500/10",
    DELETE: "text-rose-300 border-rose-500/30 bg-rose-500/10",
  }[m as "GET" | "POST" | "PUT" | "DELETE"] ?? "text-zinc-300 border-white/10 bg-white/[0.04]";
  return (
    <span
      className={cn(
        "inline-block min-w-12 rounded border px-1.5 py-0.5 text-center text-[10px] font-semibold tracking-wider",
        tone
      )}
    >
      {m}
    </span>
  );
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="group relative my-3 overflow-hidden rounded-lg border border-white/[0.06] bg-black/40">
      <div className="flex items-center justify-between border-b border-white/[0.04] px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
        <span>{lang}</span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] text-zinc-400 transition-colors hover:bg-white/[0.05] hover:text-zinc-200"
        >
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3 text-[12.5px] leading-relaxed text-zinc-200">
        <code>{code}</code>
      </pre>
    </div>
  );
}
