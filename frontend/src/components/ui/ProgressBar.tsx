import { cn } from "../../utils/cn";

interface ProgressBarProps {
  value: number;
  max: number;
  className?: string;
}

export function ProgressBar({
  value,
  max,
  className,
}: ProgressBarProps) {
  const pct =
    max > 0
      ? Math.min(
        100,
        (value / max) * 100
      )
      : 0;

  return (
    <div
      className={cn(
        "h-1.5 w-full overflow-hidden rounded-full bg-slate-100",
        className
      )}
    >
      <div
        className="h-full rounded-full bg-brand-500 transition-all duration-500 ease-out"
        style={{
          width: `${pct}%`,
        }}
      />
    </div>
  );
}