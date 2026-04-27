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
  const processedTotal = progress.prices_total > 0 ? progress.prices_total : progress.routes_total;
  const processedDone = progress.prices_total > 0 ? progress.prices_done : progress.routes_done;
  const processedStarted =
    progress.prices_total > 0
      ? Math.max(progress.prices_started, progress.prices_done)
      : progress.routes_done;
  const activeSearches =
    progress.prices_total > 0
      ? Math.max(progress.prices_started - progress.prices_done, 0)
      : 0;
  const pct =
    processedTotal > 0
      ? Math.round(
        (processedStarted /
          processedTotal) *
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
          {processedDone > 0 ? `${pct}% Processed` : "Starting collection"}
        </div>
      </div>

      {/* Progress */}
      <div className="mt-3">
        <div className="mb-1.5 flex items-center justify-between text-xs text-brand-700">
          <span>
            {processedDone}/{processedTotal} completed
          </span>

          <span>
            {progress.dates_scraped.toLocaleString()} prices saved
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
              Searching{" "}
              <span className="font-mono font-semibold text-brand-900">
                {progress.current_origin}
              </span>
              {progress.current_destination ? (
                <>
                  {" -> "}
                  <span className="font-mono font-semibold text-brand-900">
                    {progress.current_destination}
                  </span>
                </>
              ) : null}
              {progress.current_date ? <> on {progress.current_date}</> : null}
            </>
          ) : (
            "Preparing routes..."
          )}
        </div>

        {activeSearches > 0 ? (
          <div className="inline-flex items-center gap-1 text-brand-700">
            <Activity className="h-3.5 w-3.5" />
            {activeSearches} search{activeSearches === 1 ? "" : "es"} in flight
          </div>
        ) : null}

        {progress.routes_failed > 0 || progress.prices_failed > 0 ? (
          <div className="inline-flex items-center gap-1 text-red-600">
            <AlertTriangle className="h-3.5 w-3.5" />
            {progress.prices_failed > 0
              ? `${progress.prices_failed} checks failed`
              : `${progress.routes_failed} routes failed`}
          </div>
        ) : null}
      </div>
    </div>
  );
}
