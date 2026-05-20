import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CreativeBrief, ScriptOutput, ShotPlan } from "@/types";

export function useCreateRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      topic: string;
      provider?: string;
      draft?: boolean;
      runId?: string;
      soulId?: string | null;
      brief?: Partial<CreativeBrief> | null;
      voiceless?: boolean;
      useKeyframes?: boolean;
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

export function useUpdateShotPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId, plan }: { runId: string; plan: ShotPlan }) =>
      api.updateShotPlan(runId, plan),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["run", vars.runId] });
    },
  });
}

export function useRefineShot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      shotIndex,
      instruction,
    }: {
      runId: string;
      shotIndex: number;
      instruction: string;
    }) => api.refineShot(runId, shotIndex, instruction),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["run", vars.runId] });
    },
  });
}

export function useRegenerateClip() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      clipIndex,
      extraInstruction,
    }: {
      runId: string;
      clipIndex: number;
      extraInstruction?: string;
    }) => api.regenerateClip(runId, clipIndex, extraInstruction),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["run", vars.runId] });
    },
  });
}

export function useReassembleRun() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ runId }: { runId: string }) => api.reassembleRun(runId),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ["runs"] });
      qc.invalidateQueries({ queryKey: ["run", vars.runId] });
    },
  });
}
