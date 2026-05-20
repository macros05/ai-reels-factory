import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Character } from "@/types";

const KEY = ["characters"] as const;

export function useCharacters() {
  return useQuery({
    queryKey: KEY,
    queryFn: () => api.listCharacters(),
    // Poll while anything is training so the UI flips to "ready" without a
    // manual refresh; once everything is settled, back off.
    refetchInterval: (q) => {
      const list = q.state.data?.characters;
      if (!list) return 5000;
      return list.some((c) => c.status === "training") ? 5000 : false;
    },
  });
}

export function useCreateCharacter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      name: string;
      soul_model: Character["soul_model"];
      image_uuids: string[];
      preview_path?: string | null;
    }) => api.createCharacter(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useDeleteCharacter() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (soulId: string) => api.deleteCharacter(soulId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: KEY });
    },
  });
}

export function useHiggsfieldStatus() {
  return useQuery({
    queryKey: ["higgsfield-status"],
    queryFn: () => api.higgsfieldStatus(),
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  });
}
