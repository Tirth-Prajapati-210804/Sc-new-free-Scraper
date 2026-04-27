import { type LucideIcon } from "lucide-react";

import { cn } from "../utils/cn";

import { Card } from "./ui/Card";

interface StatCardProps {
  label: string;
  value: string | number;
  icon: LucideIcon;
  valueClassName?: string;
  subtitle?: string;
}

export function StatCard({
  label,
  value,
  icon: Icon,
  valueClassName,
  subtitle,
}: StatCardProps) {
  return (
    <Card className="group p-[18px] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_45px_-28px_rgba(79,70,229,0.28)]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            {label}
          </p>

          <p
            className={cn(
              "mt-3 truncate text-[28px] font-bold leading-none tracking-tight text-slate-950",
              valueClassName,
            )}
          >
            {value}
          </p>

          {subtitle ? (
            <p className="mt-2 truncate text-xs font-medium text-slate-400">
              {subtitle}
            </p>
          ) : null}
        </div>

        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition group-hover:scale-105">
          <Icon className="h-4.5 w-4.5" />
        </div>
      </div>
    </Card>
  );
}
