import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ReferenceKind } from "@/types";

export function useUploadReference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      kind,
      file,
    }: {
      runId: string;
      kind: ReferenceKind;
      file: File;
    }) => api.uploadReference(runId, kind, file),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["references", vars.runId] }),
  });
}

export function useYoutubeReference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      kind,
      url,
    }: {
      runId: string;
      kind: "script" | "voice" | "music";
      url: string;
    }) => api.addYoutubeReference(runId, kind, url),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ["references", vars.runId] }),
  });
}

export function useReferences(runId: string | null) {
  return useQuery({
    queryKey: ["references", runId],
    queryFn: () => api.listReferences(runId!),
    enabled: !!runId,
  });
}
