import { CheckCircle2, Clock, Loader2, Pencil, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/types";

const LABEL: Record<RunStatus, string> = {
  pending: "En cola",
  running: "Generando",
  script_ready: "Editar guion",
  done: "Listo",
  failed: "Error",
};

export function StatusBadge({ status }: { status: RunStatus }) {
  if (status === "done")
    return (
      <Badge variant="done">
        <CheckCircle2 className="size-3" />
        {LABEL.done}
      </Badge>
    );
  if (status === "running")
    return (
      <Badge variant="running">
        <Loader2 className="size-3 animate-spin" />
        {LABEL.running}
      </Badge>
    );
  if (status === "script_ready")
    return (
      <Badge variant="accent">
        <Pencil className="size-3" />
        {LABEL.script_ready}
      </Badge>
    );
  if (status === "failed")
    return (
      <Badge variant="failed">
        <XCircle className="size-3" />
        {LABEL.failed}
      </Badge>
    );
  return (
    <Badge variant="pending">
      <Clock className="size-3" />
      {LABEL.pending}
    </Badge>
  );
}
