import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400/50 focus-visible:ring-offset-2 focus-visible:ring-offset-[color:var(--color-ink-950)] disabled:opacity-50 disabled:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          // Solid violet with a subtle conic glow under the surface so it
          // reads as a hero CTA but not as a neon button.
          "bg-violet-500 text-white hover:bg-violet-400 shadow-[0_8px_30px_-12px_rgb(139_92_246/0.7)] hover:shadow-[0_10px_38px_-12px_rgb(139_92_246/0.8)]",
        secondary:
          "bg-white/[0.05] text-zinc-100 hover:bg-white/[0.08] border border-white/[0.08] hover:border-white/[0.14]",
        outline:
          "border border-white/[0.10] bg-transparent text-zinc-100 hover:bg-white/[0.04] hover:border-white/[0.18]",
        ghost:
          "bg-transparent text-zinc-300 hover:bg-white/[0.05] hover:text-zinc-50",
        destructive:
          "bg-rose-500/90 text-white hover:bg-rose-500 shadow-[0_8px_30px_-12px_rgb(244_63_94/0.6)]",
        glass:
          "glass text-zinc-100 hover:bg-white/[0.06]",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-7 text-base font-semibold",
        xl: "h-14 px-8 text-base font-semibold tracking-tight",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  }
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
