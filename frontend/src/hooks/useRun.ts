import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRun(id: string | undefined) {
  return useQuery({
    queryKey: ["run", id],
    queryFn: () => api.getRun(id!),
    enabled: Boolean(id),
    refetchInterval: (query) => {
      const r = query.state.data;
      if (!r) return 3000;
      return r.status === "running" || r.status === "pending" ? 3000 : false;
    },
  });
}
