import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium",
  {
    variants: {
      variant: {
        default: "bg-zinc-800 text-zinc-200 border border-zinc-700",
        accent: "bg-violet-500/15 text-violet-300 border border-violet-500/30",
        done: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
        running: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
        failed: "bg-rose-500/15 text-rose-300 border border-rose-500/30",
        pending: "bg-zinc-500/15 text-zinc-400 border border-zinc-500/30",
        outline: "border border-zinc-700 text-zinc-300",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, ...props }, ref) => (
    <span ref={ref} className={cn(badgeVariants({ variant }), className)} {...props} />
  )
);
Badge.displayName = "Badge";
