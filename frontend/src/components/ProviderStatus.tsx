import {
  CheckCircle2,
  PlugZap,
} from "lucide-react";

import { type HealthResponse } from "../types/stats";
import { Card } from "./ui/Card";

interface ProviderStatusProps {
  health?: HealthResponse;
}

export function ProviderStatus({
  health,
}: ProviderStatusProps) {
  const providerStatus =
    health?.provider_status ?? {};

  const providers =
    Object.entries(providerStatus);

  if (providers.length === 0) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-slate-100 text-slate-500">
            <PlugZap className="h-4 w-4" />
          </div>

          <div>
            <p className="text-sm font-semibold text-slate-900">
              Provider Status
            </p>

            <p className="text-sm text-slate-500">
              No provider data available
            </p>
          </div>
        </div>
      </Card>
    );
  }

  const readyCount = providers.filter(
    ([, status]) =>
      status === "configured" || status === "active"
  ).length;

  return (
    <Card className="p-5">
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[15px] font-semibold text-slate-900">
            Provider Status
          </p>
        </div>

        <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          {readyCount}/{providers.length} Ready
        </div>
      </div>

      {/* Inline providers */}
      <div className="mt-4 flex flex-wrap gap-2.5">
        {providers.map(
          ([name, status]) => {
            const active =
              status === "configured" || status === "active";

            return (
              <div
                key={name}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2"
              >
                {active ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <span className="h-2 w-2 rounded-full bg-slate-300" />
                )}

                <span className="text-sm font-medium capitalize text-slate-800">
                  {name}
                </span>

                <span
                  className={`text-xs font-medium ${active
                    ? "text-emerald-600"
                    : "text-slate-400"
                    }`}
                >
                  {status}
                </span>
              </div>
            );
          }
        )}
      </div>
    </Card>
  );
}
