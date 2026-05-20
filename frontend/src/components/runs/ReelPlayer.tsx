import { mediaUrl } from "@/lib/api";

export function ReelPlayer({ runId }: { runId: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-zinc-800 bg-black">
      <video
        src={mediaUrl(runId, "video.mp4")}
        controls
        autoPlay
        muted
        playsInline
        className="aspect-[9/16] w-full bg-black object-contain"
      />
    </div>
  );
}
