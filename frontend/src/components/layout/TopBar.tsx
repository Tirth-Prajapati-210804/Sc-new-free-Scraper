import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Clock3,
  Database,
} from "lucide-react";

import { fetchHealth } from "../../api/stats";
import { formatRelativeTime } from "../../utils/format";

interface TopBarProps {
  title: string;
}

export function TopBar({
  title,
}: TopBarProps) {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const isRunning =
    health?.scheduler_running ?? false;

  return (
    <header className="sticky top-0 z-20 bg-transparent px-4 pt-4 sm:px-6 lg:px-8">
      <div className="flex min-h-[78px] items-center justify-between gap-3 rounded-[28px] border border-slate-200/80 bg-white/85 px-5 py-3 shadow-[0_18px_40px_-34px_rgba(15,23,42,0.45)] backdrop-blur">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Workspace
          </p>

          <h1 className="truncate text-[22px] font-bold leading-tight text-slate-900">
            {title}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <StatusPill
            icon={
              <Activity className="h-3.5 w-3.5" />
            }
            active={isRunning}
            label={
              isRunning
                ? "Scheduler Running"
                : "Scheduler Stopped"
            }
          />

          {health && (
            <StatusPill
              icon={
                <Database className="h-3.5 w-3.5" />
              }
              active={
                health.database_status ===
                "ok"
              }
              label={`DB ${health.database_status}`}
            />
          )}
        </div>
      </div>
    </header>
  );
}

export function TopBarWithLastRun({
  title,
  lastRunAt,
}: {
  title: string;
  lastRunAt?: string | null;
}) {
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const isRunning =
    health?.scheduler_running ?? false;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/90 backdrop-blur">
      <div className="flex min-h-[56px] items-center justify-between gap-3 px-5 py-2 md:px-6">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Workspace
          </p>

          <h1 className="truncate text-lg font-semibold leading-tight text-slate-900">
            {title}
          </h1>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {lastRunAt && (
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
              <Clock3 className="h-3.5 w-3.5" />
              Last run{" "}
              {formatRelativeTime(
                lastRunAt
              )}
            </div>
          )}

          <StatusPill
            icon={
              <Activity className="h-3.5 w-3.5" />
            }
            active={isRunning}
            label={
              isRunning
                ? "Scheduler Active"
                : "Scheduler Idle"
            }
          />
        </div>
      </div>
    </header>
  );
}

function StatusPill({
  icon,
  active,
  label,
}: {
  icon: React.ReactNode;
  active: boolean;
  label: string;
}) {
  return (
    <div
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium ${active
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-indigo-200 bg-indigo-50 text-brand-700"
        }`}
    >
      <span
        className={
          active
            ? "text-emerald-600"
            : "text-slate-500"
        }
      >
        {icon}
      </span>

      {label}
    </div>
  );
}
