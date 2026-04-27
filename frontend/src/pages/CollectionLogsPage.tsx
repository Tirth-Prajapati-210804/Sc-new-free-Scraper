import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, AlertTriangle, Square } from "lucide-react";
import { useMemo, useState } from "react";

import {
  fetchCollectionRuns,
  fetchScrapeLogs,
  getCollectionStatus,
  stopCollection,
} from "../api/collection";
import { listRouteGroups } from "../api/route-groups";

import { CollectionRunsTable } from "../components/CollectionRunsTable";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ScrapeLogsTable } from "../components/ScrapeLogsTable";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";

import { useToast } from "../context/ToastContext";

import type { ScrapeLogEntry } from "../types/price";
import { usePageTitle } from "../utils/usePageTitle";

export function CollectionLogsPage() {
  usePageTitle("Collection Logs");

  const qc = useQueryClient();
  const { showToast } = useToast();

  const [filterGroupId, setFilterGroupId] = useState("");
  const [filterProvider, setFilterProvider] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const statusQuery = useQuery({
    queryKey: ["collection-status"],
    queryFn: getCollectionStatus,
    refetchInterval: (query) => (query.state.data?.is_collecting ? 3_000 : 15_000),
  });

  const runsQuery = useQuery({
    queryKey: ["collection-runs"],
    queryFn: () => fetchCollectionRuns(20),
    refetchInterval: statusQuery.data?.is_collecting ? 5_000 : 30_000,
  });

  const logsQuery = useQuery({
    queryKey: ["scrape-logs", filterGroupId],
    queryFn: () =>
      fetchScrapeLogs({
        route_group_id: filterGroupId || undefined,
        limit: 100,
      }),
    refetchInterval: 30_000,
  });

  const stopMut = useMutation({
    mutationFn: stopCollection,
    onSuccess: (data) => {
      if (data.status === "stop_requested") {
        showToast("Stop signal sent.", "success");
      } else {
        showToast("No collection is running", "info");
      }

      qc.invalidateQueries({ queryKey: ["collection-status"] });
      qc.invalidateQueries({ queryKey: ["collection-runs"] });
    },
    onError: () => showToast("Failed to stop collection", "error"),
  });

  const filteredLogs = useMemo<ScrapeLogEntry[]>(() => {
    let logs = logsQuery.data ?? [];

    if (filterProvider) {
      logs = logs.filter((log) => log.provider === filterProvider);
    }

    if (filterStatus) {
      logs = logs.filter((log) => log.status === filterStatus);
    }

    return logs;
  }, [filterProvider, filterStatus, logsQuery.data]);

  const providers = useMemo(() => {
    const set = new Set((logsQuery.data ?? []).map((log) => log.provider));
    return [...set].sort();
  }, [logsQuery.data]);

  const isCollecting = statusQuery.data?.is_collecting ?? false;
  const last = runsQuery.data?.[0];

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <section className="rounded-[30px] border border-slate-200 bg-white px-6 py-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Operations
              </p>
              <h1 className="mt-1 text-3xl font-bold text-slate-950">Collection Logs</h1>
              <p className="mt-2 text-sm text-slate-500">
                Review collection runs, failures, and scrape activity.
              </p>
            </div>

            {isCollecting ? (
              <div className="flex items-center gap-2">
                <div className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-2 text-xs font-medium text-brand-700">
                  <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" />
                  Running
                </div>
                <Button variant="danger" size="sm" onClick={() => stopMut.mutate()} loading={stopMut.isPending}>
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </Button>
              </div>
            ) : null}
          </div>
        </section>

        {statusQuery.isError ? (
          <InlineError text="Failed to load collection status." />
        ) : null}

        {runsQuery.isError ? (
          <InlineError text="Failed to load collection runs." />
        ) : null}

        {logsQuery.isError ? (
          <InlineError text="Failed to load scrape logs." />
        ) : null}

        {last?.errors?.length ? (
          <div className="rounded-[20px] border border-red-200 bg-red-50 px-4 py-3">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 text-red-600" />
              <div>
                <p className="text-sm font-semibold text-red-800">
                  Last collection had {last.errors.length} failure(s)
                </p>
                <ul className="mt-1 space-y-1 text-xs text-red-700">
                  {last.errors.slice(0, 5).map((error, index) => (
                    <li key={index} className="font-mono">
                      {error}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        ) : null}

        <Card className="space-y-4 p-5">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-slate-500" />
            <h2 className="text-[15px] font-semibold text-slate-900">Collection Runs</h2>
          </div>
          <CollectionRunsTable
            runs={runsQuery.data ?? []}
            isLoading={runsQuery.isLoading}
            onStop={() => stopMut.mutate()}
            stopping={stopMut.isPending}
          />
        </Card>

        <Card className="space-y-4 p-0 overflow-hidden">
          <div className="border-b border-slate-200 px-6 py-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div className="min-w-0">
                <h2 className="text-[15px] font-semibold text-slate-900">Recent Scrape Logs</h2>
                <p className="text-sm text-slate-500">Latest 100 entries</p>
              </div>

              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 xl:w-[560px]">
                <Select value={filterGroupId} onChange={(e) => setFilterGroupId(e.target.value)}>
                  <option value="">All groups</option>
                  {groupsQuery.data?.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.name}
                    </option>
                  ))}
                </Select>

                <Select value={filterProvider} onChange={(e) => setFilterProvider(e.target.value)}>
                  <option value="">All providers</option>
                  {providers.map((provider) => (
                    <option key={provider} value={provider}>
                      {provider}
                    </option>
                  ))}
                </Select>

                <Select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
                  <option value="">All statuses</option>
                  <option value="success">Success</option>
                  <option value="error">Error</option>
                  <option value="no_results">No results</option>
                  <option value="rate_limited">Rate limited</option>
                </Select>
              </div>
            </div>

            {(logsQuery.data?.length ?? 0) !== filteredLogs.length ? (
              <p className="mt-3 text-xs text-slate-400">
                {filteredLogs.length} / {logsQuery.data?.length ?? 0} shown
              </p>
            ) : null}
          </div>

          <div className="px-6 py-5">
            <ScrapeLogsTable logs={filteredLogs} isLoading={logsQuery.isLoading} />
          </div>
        </Card>
      </div>
    </ErrorBoundary>
  );
}

function InlineError({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {text}
    </div>
  );
}
