import {
  type SelectHTMLAttributes,
} from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "../../utils/cn";

interface SelectProps
  extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
}

export function Select({
  label,
  className,
  id,
  children,
  ...props
}: SelectProps) {
  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={id}
          className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500"
        >
          {label}
        </label>
      )}

      <div className="relative">
        <select
          id={id}
          className={cn(
            "block h-11 w-full appearance-none rounded-2xl border border-slate-200 bg-white px-4 pr-10 text-sm text-slate-700 shadow-sm transition",
            "focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-500/10",
            "hover:border-slate-300 disabled:bg-slate-50 disabled:text-slate-400",
            className
          )}
          {...props}
        >
          {children}
        </select>

        <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
      </div>
    </div>
  );
}
