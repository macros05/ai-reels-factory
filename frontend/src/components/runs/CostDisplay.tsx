import { formatCredits } from "@/lib/utils";

export function CostDisplay({
  credits,
  className = "",
}: {
  credits: number | null | undefined;
  className?: string;
}) {
  return (
    <span className={`mono text-xs text-zinc-400 ${className}`}>
      {formatCredits(credits)}
    </span>
  );
}
