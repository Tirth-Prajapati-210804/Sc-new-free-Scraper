import {
  Activity,
  AlertTriangle,
  PlaneTakeoff,
} from "lucide-react";

import type { CollectionProgress } from "../api/collection";

interface Props {
  progress: CollectionProgress;
}

export function CollectionProgressBar({
  progress,
}: Props) {
  const pct =
    progress.routes_total > 0
      ? Math.round(
        (progress.routes_done /
          progress.routes_total) *
        100
      )
      : 0;

  return (
    <div className="rounded-[20px] border border-brand-100 bg-brand-50 px-4 py-3">
      {/* Top Row */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-white text-brand-600 ring-1 ring-brand-100">
            <PlaneTakeoff className="h-4 w-4" />
          </div>

          <div>
            <p className="text-sm font-semibold text-brand-900">
              Collecting Prices
            </p>

            <p className="text-xs text-brand-700">
              Live scraping session
            </p>
          </div>
        </div>

        <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1.5 text-xs font-semibold text-brand-700">
          <Activity className="h-3.5 w-3.5" />
          {pct}% Complete
        </div>
      </div>

      {/* Progress */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-xs text-brand-700">
          <span>
            {progress.routes_done}/
            {progress.routes_total} routes
          </span>

          <span>
            {progress.dates_scraped.toLocaleString()} prices
          </span>
        </div>

        <div className="h-2 w-full overflow-hidden rounded-full bg-brand-100">
          <div
            className="h-full rounded-full bg-brand-500 transition-all duration-500"
            style={{
              width: `${pct}%`,
            }}
          />
        </div>
      </div>

      {/* Bottom Row */}
      <div className="mt-2 flex flex-col gap-1 text-xs sm:flex-row sm:items-center sm:justify-between">
        <div className="text-brand-700">
          {progress.current_origin ? (
            <>
              Current origin:{" "}
              <span className="font-mono font-semibold text-brand-900">
                {
                  progress.current_origin
                }
              </span>
            </>
          ) : (
            "Preparing routes..."
          )}
        </div>

        {progress.routes_failed > 0 && (
          <div className="inline-flex items-center gap-1 text-red-600">
            <AlertTriangle className="h-3.5 w-3.5" />
            {progress.routes_failed} failed
          </div>
        )}
      </div>
    </div>
  );
}
