import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api.providers(),
    staleTime: 1000 * 60 * 5,
  });
}
