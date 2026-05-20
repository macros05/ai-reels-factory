import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRuns() {
  return useQuery({
    queryKey: ["runs"],
    queryFn: async () => (await api.listRuns()).runs,
    refetchInterval: (query) => {
      const runs = query.state.data;
      if (!runs) return 5000;
      const active = runs.some((r) => r.status === "running" || r.status === "pending");
      return active ? 3000 : 10000;
    },
  });
}
