import {
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";

import { cn } from "../../utils/cn";

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?:
  | "primary"
  | "secondary"
  | "ghost"
  | "danger";

  size?: "sm" | "md" | "lg";

  children: ReactNode;
  loading?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  children,
  loading = false,
  disabled,
  className,
  ...props
}: ButtonProps) {
  const base = `
    inline-flex items-center justify-center gap-2
    whitespace-nowrap rounded-2xl
    font-medium
    transition-all duration-200
    focus:outline-none focus:ring-2 focus:ring-brand-500/25
    disabled:pointer-events-none disabled:opacity-55
    select-none
  `;

  const sizes = {
    sm: "h-9 px-3.5 text-xs",
    md: "h-10 px-4 text-sm",
    lg: "h-11 px-5 text-sm",
  };

  const variants = {
    primary: `
      bg-brand-600 text-white
      shadow-[0_12px_26px_-18px_rgba(79,70,229,0.95)]
      hover:-translate-y-[1px] hover:bg-brand-700 hover:shadow-[0_16px_28px_-18px_rgba(79,70,229,0.95)]
      active:translate-y-0 active:bg-brand-800
    `,

    secondary: `
      border border-slate-200 bg-white text-slate-700
      hover:border-slate-300 hover:bg-slate-50
      active:bg-slate-100
    `,

    ghost: `
      bg-transparent text-slate-600
      hover:bg-slate-100 hover:text-slate-900
      active:bg-slate-200
    `,

    danger: `
      border border-red-200 bg-red-50 text-red-600
      hover:bg-red-100 hover:text-red-700
      active:bg-red-800
    `,
  };

  return (
    <button
      className={cn(
        base,
        sizes[size],
        variants[variant],
        className
      )}
      disabled={disabled || loading}
      aria-disabled={
        disabled || loading
      }
      {...props}
    >
      {loading && (
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      )}

      {children}
    </button>
  );
}
