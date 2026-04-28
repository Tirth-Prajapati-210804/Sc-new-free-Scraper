import { useMemo } from "react";

import type { RouteGroupProgress } from "../types/route-group";
import { formatFreshnessLabel, formatNumber } from "../utils/format";

interface DateCoverageGridProps {
  progress: RouteGroupProgress;
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

function toIso(date: Date): string {
  return date.toISOString().slice(0, 10);
}

interface MonthGroup {
  label: string;
  days: { iso: string; hasData: boolean; isToday: boolean }[];
}

export function DateCoverageGrid({ progress }: DateCoverageGridProps) {
  const scrapedSet = useMemo(() => new Set(progress.scraped_dates), [progress.scraped_dates]);

  const originCount = Object.keys(progress.per_origin).length || 1;
  const daySpan = useMemo(() => {
    if (progress.scraped_dates.length >= 2) {
      const sorted = [...progress.scraped_dates].sort();
      const first = new Date(`${sorted[0]}T00:00:00`);
      const last = new Date(`${sorted[sorted.length - 1]}T00:00:00`);
      const diff = Math.round((last.getTime() - first.getTime()) / 86_400_000) + 1;
      return Math.max(diff, 30);
    }
    const approx = originCount > 0 ? Math.round(progress.total_dates / originCount) : 90;
    return Math.max(approx, 30);
  }, [originCount, progress.scraped_dates, progress.total_dates]);

  const today = useMemo(() => {
    const value = new Date();
    value.setHours(0, 0, 0, 0);
    return value;
  }, []);

  const startDate = useMemo(() => {
    if (progress.scraped_dates.length > 0) {
      const sorted = [...progress.scraped_dates].sort();
      return new Date(`${sorted[0]}T00:00:00`);
    }
    return addDays(today, 1);
  }, [progress.scraped_dates, today]);

  const months = useMemo<MonthGroup[]>(() => {
    const groups: MonthGroup[] = [];
    let current = new Date(startDate);

    for (let i = 0; i < daySpan; i++) {
      const iso = toIso(current);
      const monthKey = current.toLocaleDateString("en-US", { month: "short", year: "numeric" });
      const isToday = iso === toIso(today);
      let group = groups.find((entry) => entry.label === monthKey);
      if (!group) {
        group = { label: monthKey, days: [] };
        groups.push(group);
      }
      group.days.push({ iso, hasData: scrapedSet.has(iso), isToday });
      current = addDays(current, 1);
    }

    return groups;
  }, [daySpan, scrapedSet, startDate, today]);

  if (progress.scraped_dates.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">
            0 / {formatNumber(progress.total_dates)} dates collected
          </span>
          <span className="font-semibold text-slate-400">0.0%</span>
        </div>
        <div className="rounded-lg border border-dashed border-slate-200 py-10 text-center">
          <p className="text-sm text-slate-400">No dates scraped yet.</p>
          <p className="mt-1 text-xs text-slate-300">Trigger a collection to start.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-medium text-slate-700">
              {formatNumber(progress.dates_with_data)}{" "}
              <span className="font-normal text-slate-500">
                / {formatNumber(progress.total_dates)} dates collected
              </span>
            </span>
            <span className="font-semibold text-brand-600">
              {progress.coverage_percent.toFixed(1)}%
            </span>
          </div>
          <p className="text-xs text-slate-500">{formatFreshnessLabel(progress.last_scraped_at)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-brand-500" />
            Collected
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-3 w-3 rounded-sm bg-slate-200" />
            Not yet collected
          </span>
        </div>
      </div>

      <div className="space-y-4">
        {months.map((month) => (
          <div key={month.label}>
            <p className="mb-1.5 text-xs font-medium text-slate-500">{month.label}</p>
            <div className="flex flex-wrap gap-1">
              {month.days.map(({ iso, hasData, isToday }) => (
                <div
                  key={iso}
                  title={iso}
                  className={[
                    "h-4 w-4 rounded-[4px] transition-colors",
                    hasData ? "bg-brand-500 hover:bg-brand-600" : "bg-slate-200 hover:bg-slate-300",
                    isToday ? "ring-2 ring-amber-400 ring-offset-1" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                />
              ))}
            </div>
          </div>
        ))}
      </div>

      {Object.keys(progress.per_origin).length > 0 ? (
        <div className="border-t border-slate-100 pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
            Per Origin
          </p>
          <div className="space-y-2">
            {Object.entries(progress.per_origin).map(([origin, data]) => {
              const pct = data.total > 0 ? Math.round((data.collected / data.total) * 100) : 0;
              return (
                <div key={origin} className="flex items-center gap-3">
                  <span className="w-10 font-mono text-xs font-medium text-slate-700">
                    {origin}
                  </span>
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <div
                      className="h-full rounded-full bg-brand-500 transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="w-24 text-right text-xs text-slate-500">
                    {formatNumber(data.collected)}/{formatNumber(data.total)}
                  </span>
                  <span className="w-9 text-right text-xs font-medium text-slate-600">
                    {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
