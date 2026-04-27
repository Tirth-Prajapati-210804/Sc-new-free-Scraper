import { cn } from "../../utils/cn";

type BadgeVariant = "green" | "amber" | "red" | "gray";

interface BadgeProps {
  variant: BadgeVariant;
  label: string;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  green: "bg-green-50 text-green-700 ring-green-600/20",
  amber: "bg-amber-50 text-amber-700 ring-amber-600/20",
  red: "bg-red-50 text-red-700 ring-red-600/20",
  gray: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export function Badge({ variant, label, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset",
        variantStyles[variant],
        className,
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          variant === "green" && "bg-green-500",
          variant === "amber" && "bg-amber-500",
          variant === "red" && "bg-red-500",
          variant === "gray" && "bg-slate-400",
        )}
      />
      {label}
    </span>
  );
}
