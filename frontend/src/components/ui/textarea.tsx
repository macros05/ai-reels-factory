import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "flex min-h-[80px] w-full rounded-lg border border-white/[0.08] bg-white/[0.03] px-3.5 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 transition-all duration-150 hover:border-white/[0.14] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/40 focus-visible:border-violet-400/50 focus-visible:bg-white/[0.05] disabled:opacity-50 resize-none leading-relaxed",
      className
    )}
    {...props}
  />
));
Textarea.displayName = "Textarea";
