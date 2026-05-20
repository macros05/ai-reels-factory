import { useEffect, useState } from "react";
import { Copy, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function CaptionEditor({ caption }: { caption: string }) {
  const [value, setValue] = useState(caption);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setValue(caption);
  }, [caption]);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      toast.success("Caption copiado");
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("No se pudo copiar");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-zinc-300">Caption</label>
        <Button variant="ghost" size="sm" onClick={handleCopy} type="button">
          {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={6}
        className="mono text-xs"
      />
    </div>
  );
}
