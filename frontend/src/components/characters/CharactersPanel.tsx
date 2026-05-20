import { useState, type ChangeEvent } from "react";
import {
  Image as ImageIcon,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Upload,
  User,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  useCharacters,
  useCreateCharacter,
  useDeleteCharacter,
} from "@/hooks/useCharacters";
import { api, ApiError } from "@/lib/api";
import { cn, relativeTime } from "@/lib/utils";
import type { Character } from "@/types";

const MIN_PHOTOS = 5;
const MAX_PHOTOS = 20;

interface PendingPhoto {
  file: File;
  upload_id?: string;
  preview_url: string;
  local_path?: string;
  uploading: boolean;
  error?: string;
}

export function CharactersPanel() {
  const { data, isLoading } = useCharacters();
  const characters = data?.characters ?? [];
  const [creating, setCreating] = useState(false);

  return (
    <Card className="border-zinc-800">
      <CardContent className="flex flex-col gap-5 p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">Characters</h2>
            <p className="mt-1 text-xs text-zinc-500">
              Entrena un Soul ID con 5-20 fotos para fijar la misma cara entre reels. Tarda
              ~3-5 min y se reutiliza siempre que lo selecciones al lanzar.
            </p>
          </div>
          <Button
            size="sm"
            type="button"
            onClick={() => setCreating((c) => !c)}
            variant={creating ? "outline" : "default"}
          >
            {creating ? "Cancelar" : (
              <>
                <Plus className="size-4" /> Nuevo character
              </>
            )}
          </Button>
        </div>

        {creating && <CharacterCreator onDone={() => setCreating(false)} />}

        <CharacterList characters={characters} loading={isLoading} />
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// list
// ---------------------------------------------------------------------------

function CharacterList({ characters, loading }: { characters: Character[]; loading: boolean }) {
  const del = useDeleteCharacter();

  if (loading) {
    return (
      <div className="flex items-center justify-center py-6 text-sm text-zinc-500">
        <Loader2 className="mr-2 size-4 animate-spin" /> Cargando…
      </div>
    );
  }
  if (characters.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
        Aún no has entrenado ningún character.
        <br />
        Empieza por "Nuevo character" arriba.
      </div>
    );
  }
  return (
    <ul className="flex flex-col gap-2">
      {characters.map((c) => (
        <li
          key={c.soul_id}
          className="flex items-center justify-between gap-3 rounded-lg border border-zinc-800 bg-zinc-900/40 px-3 py-2.5"
        >
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-zinc-800/60">
              <User className="size-5 text-zinc-400" />
            </div>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-zinc-100">{c.name}</p>
              <p className="mono truncate text-[11px] text-zinc-500">
                {c.soul_id.slice(0, 12)}… · {c.image_uuids.length} fotos ·{" "}
                {relativeTime(c.created_at)}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill status={c.status} error={c.error} />
            <button
              type="button"
              onClick={() => {
                if (!window.confirm(`Borrar el character "${c.name}"?`)) return;
                del.mutate(c.soul_id);
              }}
              className="rounded-md p-1.5 text-zinc-500 hover:bg-zinc-800 hover:text-rose-400"
              aria-label="Borrar character"
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function StatusPill({ status, error }: { status: Character["status"]; error: string | null }) {
  const map = {
    training: "border-amber-500/30 bg-amber-500/10 text-amber-300",
    ready: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    failed: "border-rose-500/30 bg-rose-500/10 text-rose-300",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        map[status]
      )}
      title={error ?? undefined}
    >
      {status === "training" && <Loader2 className="size-3 animate-spin" />}
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// creator (upload photos → submit)
// ---------------------------------------------------------------------------

function CharacterCreator({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [soulModel, setSoulModel] = useState<Character["soul_model"]>("soul-2");
  const [photos, setPhotos] = useState<PendingPhoto[]>([]);
  const create = useCreateCharacter();

  const ready = photos.filter((p) => p.upload_id);
  const canSubmit =
    name.trim().length > 0 &&
    ready.length >= MIN_PHOTOS &&
    ready.length <= MAX_PHOTOS &&
    !create.isPending;

  async function handleFiles(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // allow re-selecting the same file later
    if (!files.length) return;
    if (photos.length + files.length > MAX_PHOTOS) {
      toast.warning(`Máximo ${MAX_PHOTOS} fotos por character`);
      return;
    }

    const initial: PendingPhoto[] = files.map((file) => ({
      file,
      preview_url: URL.createObjectURL(file),
      uploading: true,
    }));
    setPhotos((cur) => [...cur, ...initial]);

    // Upload sequentially: lets the user see incremental progress and avoids
    // hammering the upload endpoint when 20 photos come in at once.
    for (const photo of initial) {
      try {
        const res = await api.uploadCharacterPhoto(photo.file);
        setPhotos((cur) =>
          cur.map((p) =>
            p.preview_url === photo.preview_url
              ? { ...p, uploading: false, upload_id: res.upload_id, local_path: res.local_path }
              : p
          )
        );
      } catch (err) {
        const msg = err instanceof ApiError ? err.message : "Error al subir";
        setPhotos((cur) =>
          cur.map((p) =>
            p.preview_url === photo.preview_url
              ? { ...p, uploading: false, error: msg }
              : p
          )
        );
        toast.error(`${photo.file.name}: ${msg}`);
      }
    }
  }

  function removePhoto(preview_url: string) {
    setPhotos((cur) => {
      const removed = cur.find((p) => p.preview_url === preview_url);
      if (removed) URL.revokeObjectURL(removed.preview_url);
      return cur.filter((p) => p.preview_url !== preview_url);
    });
  }

  async function handleSubmit() {
    const uuids = ready.map((p) => p.upload_id!);
    const preview_path = ready[0]?.local_path ?? null;
    try {
      await create.mutateAsync({
        name: name.trim(),
        soul_model: soulModel,
        image_uuids: uuids,
        preview_path,
      });
      toast.success("Character en entrenamiento", {
        description: "Se actualizará a 'ready' en 3-5 min sin que recargues.",
      });
      // Release blob URLs
      photos.forEach((p) => URL.revokeObjectURL(p.preview_url));
      setName("");
      setPhotos([]);
      onDone();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Error inesperado";
      toast.error(msg);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex-1">
          <label className="text-xs font-medium text-zinc-400">Nombre</label>
          <Input
            value={name}
            onChange={(e) => setName(e.target.value.slice(0, 80))}
            placeholder="e.g. Brand spokeswoman"
            className="mt-1"
            disabled={create.isPending}
          />
        </div>
        <div>
          <label className="text-xs font-medium text-zinc-400">Modelo</label>
          <div className="mt-1 flex gap-1">
            {(["soul-2", "soul-cinematic"] as const).map((m) => (
              <button
                key={m}
                type="button"
                disabled={create.isPending}
                onClick={() => setSoulModel(m)}
                className={cn(
                  "rounded-md border px-3 py-2 text-xs font-medium transition-colors",
                  soulModel === m
                    ? "border-violet-500/60 bg-violet-500/10 text-violet-200"
                    : "border-zinc-800 bg-zinc-900/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                )}
              >
                {m === "soul-2" ? "Soul 2.0" : "Soul Cinematic"}
              </button>
            ))}
          </div>
        </div>
      </div>

      <label
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-800 px-4 py-6 text-center transition-colors",
          "hover:border-zinc-600 hover:bg-zinc-900/40",
          create.isPending && "cursor-not-allowed opacity-50"
        )}
      >
        <Upload className="size-5 text-zinc-500" />
        <p className="text-sm text-zinc-300">Sube 5-20 fotos del rostro</p>
        <p className="text-[11px] text-zinc-500">
          jpg/png/webp · varios ángulos · sin gafas de sol ni recortes de cara
        </p>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          className="hidden"
          onChange={handleFiles}
          disabled={create.isPending}
        />
      </label>

      {photos.length > 0 && (
        <div className="grid grid-cols-5 gap-2 sm:grid-cols-7">
          {photos.map((p) => (
            <div
              key={p.preview_url}
              className="group relative aspect-square overflow-hidden rounded-md border border-zinc-800"
            >
              {/* eslint-disable-next-line jsx-a11y/img-redundant-alt */}
              <img
                src={p.preview_url}
                alt="character photo"
                className="size-full object-cover"
              />
              {p.uploading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/60">
                  <Loader2 className="size-4 animate-spin text-white" />
                </div>
              )}
              {p.error && (
                <div className="absolute inset-0 flex items-center justify-center bg-rose-900/70 p-1 text-center text-[10px] leading-tight text-rose-100">
                  {p.error}
                </div>
              )}
              {!p.uploading && (
                <button
                  type="button"
                  onClick={() => removePhoto(p.preview_url)}
                  className="absolute right-1 top-1 rounded bg-black/70 p-0.5 text-white opacity-0 transition-opacity group-hover:opacity-100"
                  aria-label="Quitar foto"
                >
                  <Trash2 className="size-3" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-zinc-500">
          <ImageIcon className="mr-1 inline size-3" />
          {ready.length}/{MAX_PHOTOS} listas · mínimo {MIN_PHOTOS}
        </p>
        <Button type="button" onClick={handleSubmit} disabled={!canSubmit}>
          {create.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" /> Lanzando…
            </>
          ) : (
            <>
              <Sparkles className="size-4" /> Entrenar character
            </>
          )}
        </Button>
      </div>
    </div>
  );
}
