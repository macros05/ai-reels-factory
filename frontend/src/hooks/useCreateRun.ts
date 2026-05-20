import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ScriptOutput } from "@/types";

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      topic: string;
      provider?: string;
      draft?: boolean;
      runId?: string;
      soulId?: string | null;
    }) => api.createRun(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}

export function useConfirmRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, script }: { runId: string; script: ScriptOutput }) =>
      api.confirmRun(runId, script),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["run", vars.runId] });
    },
  });
}
