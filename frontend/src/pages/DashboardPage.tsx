import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Database,
  Download,
  FlaskConical,
  FolderOpen,
  Globe,
  Grid2X2,
  List,
  MapPin,
  Play,
  RefreshCw,
  Search,
  Square,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import {
  fetchCollectionRuns,
  getCollectionStatus,
  stopCollection,
  triggerCollection,
  triggerGroupCollection,
} from "../api/collection";
import { getErrorMessage } from "../api/client";
import {
  downloadExport,
  getRouteGroupProgress,
  listRouteGroups,
  saveBlobAsFile,
} from "../api/route-groups";
import { fetchHealth, fetchOverviewStats } from "../api/stats";

import { CollectionProgressBar } from "../components/CollectionProgressBar";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { ProviderStatus } from "../components/ProviderStatus";
import { RouteGroupCard } from "../components/RouteGroupCard";
import { RouteGroupForm } from "../components/RouteGroupForm";
import { StatCard } from "../components/StatCard";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";

import { useToast } from "../context/ToastContext";
import type { RouteGroup } from "../types/route-group";
import { formatNumber, formatRelativeTime } from "../utils/format";
import { usePageTitle } from "../utils/usePageTitle";

export function DashboardPage() {
  usePageTitle("Dashboard");

  const { showToast } = useToast();
  const qc = useQueryClient();

  const [triggering, setTriggering] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "paused">("all");
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");

  const wasCollecting = useRef(false);

  const statsQuery = useQuery({
    queryKey: ["stats"],
    queryFn: fetchOverviewStats,
    refetchInterval: 60_000,
  });

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  const statusQuery = useQuery({
    queryKey: ["collection-status"],
    queryFn: getCollectionStatus,
    refetchInterval: (query) => (query.state.data?.is_collecting ? 3_000 : 15_000),
  });

  const stopMut = useMutation({
    mutationFn: stopCollection,
    onSuccess: () => {
      showToast("Stop signal sent", "success");
      qc.invalidateQueries({ queryKey: ["collection-status"] });
    },
    onError: (error) => showToast(getErrorMessage(error, "Failed to stop collection"), "error"),
  });

  const isCollecting = statusQuery.data?.is_collecting ?? false;
  const stats = statsQuery.data;
  const groups = useMemo(() => groupsQuery.data ?? [], [groupsQuery.data]);
  const health = healthQuery.data;

  useEffect(() => {
    if (wasCollecting.current && !isCollecting) {
      fetchCollectionRuns(1)
        .then((runs) => {
          const last = runs[0];
          if (!last) return;

          if (last.status === "completed") {
            const errors = last.routes_failed ?? 0;
            const success = last.routes_success ?? 0;

            if (errors > 0) {
              showToast(
                `Collection finished - ${success} prices collected, ${errors} route(s) failed.`,
                "error",
              );
            } else {
              showToast(
                `Collection finished - ${success} prices collected successfully.`,
                "success",
              );
            }
          } else if (last.status === "stopped") {
            showToast("Collection was stopped.", "info");
          } else if (last.status === "failed") {
            showToast("Collection failed. Check Collection Logs for details.", "error");
          }

          qc.invalidateQueries({ queryKey: ["stats"] });
          qc.invalidateQueries({ queryKey: ["route-groups"] });
        })
        .catch(() => {});
    }

    wasCollecting.current = isCollecting;
  }, [isCollecting, qc, showToast]);

  const noProvider =
    !healthQuery.isLoading &&
    health?.provider_status?.searchapi !== "configured" &&
    !health?.demo_mode;

  const filteredGroups = useMemo(() => {
    return groups.filter((group) => {
      const matchesSearch =
        search.trim() === "" ||
        group.name.toLowerCase().includes(search.toLowerCase()) ||
        group.destination_label.toLowerCase().includes(search.toLowerCase()) ||
        group.origins.join(" ").toLowerCase().includes(search.toLowerCase()) ||
        group.destinations.join(" ").toLowerCase().includes(search.toLowerCase());

      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" ? group.is_active : !group.is_active);

      return matchesSearch && matchesStatus;
    });
  }, [groups, search, statusFilter]);

  async function handleTriggerAll() {
    setTriggering(true);

    try {
      const res = await triggerCollection();

      if (res.status === "already_running") {
        showToast("Collection is already running", "info");
      } else {
        showToast("Collection triggered successfully", "success");
        qc.invalidateQueries({ queryKey: ["collection-status"] });
      }
    } catch (err) {
      showToast(getErrorMessage(err, "Failed to trigger collection"), "error");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <section className="rounded-[30px] border border-slate-200 bg-white px-6 py-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                Dashboard
              </p>
              <h1 className="mt-1 text-[2.1rem] font-bold leading-none text-slate-950">
                Flight Collection Overview
              </h1>
              <p className="mt-3 text-sm text-slate-500">
                {stats?.last_collection_at
                  ? `Last run ${formatRelativeTime(stats.last_collection_at)}`
                  : "No collection has run yet"}
              </p>
            </div>

            <div className="flex flex-wrap items-center justify-start gap-2 lg:justify-end">
              <HeaderPill
                tone={isCollecting || health?.scheduler_running ? "green" : "slate"}
                icon={<Activity className="h-4 w-4" />}
              >
                {isCollecting
                  ? "Collection Running"
                  : health?.scheduler_running
                    ? "Scheduler Running"
                    : "Scheduler Idle"}
              </HeaderPill>
              <HeaderPill
                tone={health?.database_status === "ok" ? "green" : "slate"}
                icon={<Database className="h-4 w-4" />}
              >
                {health?.database_status === "ok" ? "DB ok" : "DB check"}
              </HeaderPill>
              <Button variant="secondary" onClick={() => setCreateOpen(true)}>
                New Group
              </Button>
              {isCollecting ? (
                <Button
                  variant="secondary"
                  onClick={() => stopMut.mutate()}
                  loading={stopMut.isPending}
                  className="border-red-200 text-red-600 hover:bg-red-50"
                >
                  <Square className="h-4 w-4" />
                  Stop
                </Button>
              ) : (
                <Button variant="primary" onClick={handleTriggerAll} loading={triggering}>
                  <Play className="h-4 w-4" />
                  Trigger
                </Button>
              )}
            </div>
          </div>
        </section>

        {noProvider ? (
          <Banner
            tone="amber"
            icon={<AlertTriangle className="h-4 w-4" />}
            title="No API key configured"
            text="Add SEARCHAPI_KEY or enable DEMO_MODE=true."
          />
        ) : null}

        {health?.demo_mode ? (
          <Banner
            tone="amber"
            icon={<FlaskConical className="h-4 w-4" />}
            title="Demo mode active"
            text="Prices are simulated locally."
          />
        ) : null}

        {groupsQuery.error ? (
          <Banner
            tone="amber"
            icon={<AlertTriangle className="h-4 w-4" />}
            title="Route groups could not be loaded"
            text={getErrorMessage(groupsQuery.error, "The dashboard could not load your route groups.")}
          />
        ) : null}

        {statsQuery.error ? (
          <Banner
            tone="amber"
            icon={<AlertTriangle className="h-4 w-4" />}
            title="Overview stats could not be loaded"
            text={getErrorMessage(statsQuery.error, "Current totals are temporarily unavailable.")}
          />
        ) : null}

        {healthQuery.error ? (
          <Banner
            tone="amber"
            icon={<AlertTriangle className="h-4 w-4" />}
            title="Health status could not be loaded"
            text={getErrorMessage(healthQuery.error, "Provider and database checks are temporarily unavailable.")}
          />
        ) : null}

        {isCollecting && statusQuery.data?.progress ? (
          <section className="rounded-[24px] border border-brand-100 bg-brand-50 p-3">
            <CollectionProgressBar progress={statusQuery.data.progress} />
          </section>
        ) : null}

        <section className="space-y-3">
          <SectionTitle title="Overview" subtitle="Current totals" />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {statsQuery.isLoading ? (
              [...Array(4)].map((_, index) => (
                <Skeleton key={index} className="h-24 rounded-2xl" />
              ))
            ) : (
              <>
                <StatCard label="Route Groups" value={groups.length} icon={Globe} />
                <StatCard
                  label="Prices Collected"
                  value={stats ? formatNumber(stats.total_prices_collected) : "0"}
                  icon={Database}
                />
                <StatCard label="Origins" value={stats?.total_origins ?? 0} icon={MapPin} />
                <StatCard
                  label="Last Run"
                  value={stats?.last_collection_at ? formatRelativeTime(stats.last_collection_at) : "Never"}
                  valueClassName="text-[22px] leading-tight sm:text-[24px]"
                  subtitle={stats?.last_collection_at ? "Latest collection activity" : "No completed collections yet"}
                  icon={Activity}
                />
              </>
            )}
          </div>
        </section>

        <section className="space-y-4">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <h2 className="text-[15px] font-semibold text-slate-900">Route Groups</h2>
              <p className="text-sm text-slate-500">
                {groups.length} configured | {filteredGroups.length} shown
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Search groups..."
                  className="h-10 w-[220px] rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500"
                />
              </div>

              <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
                {[
                  { id: "all", label: "All" },
                  { id: "active", label: "Active" },
                  { id: "paused", label: "Paused" },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setStatusFilter(item.id as "all" | "active" | "paused")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      statusFilter === item.id
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-400"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>

              <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
                <button
                  type="button"
                  onClick={() => setViewMode("grid")}
                  className={`flex h-8 w-8 items-center justify-center rounded-lg transition ${
                    viewMode === "grid" ? "bg-white text-brand-700 shadow-sm" : "text-slate-400"
                  }`}
                >
                  <Grid2X2 className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("list")}
                  className={`flex h-8 w-8 items-center justify-center rounded-lg transition ${
                    viewMode === "list" ? "bg-white text-brand-700 shadow-sm" : "text-slate-400"
                  }`}
                >
                  <List className="h-4 w-4" />
                </button>
              </div>

              <Button variant="primary" onClick={() => setCreateOpen(true)}>
                Add Group
              </Button>
            </div>
          </div>

          {groupsQuery.isLoading ? (
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}
            >
              {[...Array(4)].map((_, index) => (
                <Skeleton key={index} className="h-64 rounded-3xl" />
              ))}
            </div>
          ) : filteredGroups.length === 0 ? (
            <div className="rounded-[28px] border border-dashed border-slate-300 bg-white p-8 text-center">
              <FolderOpen className="mx-auto h-9 w-9 text-slate-300" />
              <h3 className="mt-3 text-base font-semibold text-slate-900">No route groups match your search</h3>
              <p className="mt-1 text-sm text-slate-500">Try a different keyword or filter.</p>
            </div>
          ) : viewMode === "grid" ? (
            <div
              className="grid gap-3"
              style={{ gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}
            >
              {filteredGroups.map((group) => (
                <RouteGroupCard key={group.id} group={group} />
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-[16px] border border-slate-200 bg-white">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-[11px] font-semibold uppercase tracking-[0.05em] text-slate-500">
                    {["Group", "Route", "Type", "Coverage", "Window", "Currency", "Status", ""].map((heading) => (
                      <th key={heading} className="whitespace-nowrap px-4 py-3">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredGroups.map((group) => (
                    <DashboardGroupRow key={group.id} group={group} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="space-y-3">
          <SectionTitle title="Provider Status" subtitle="Live integrations" />
          {healthQuery.isLoading ? (
            <Skeleton className="h-20 rounded-3xl" />
          ) : (
            <ProviderStatus health={health} />
          )}
        </section>
      </div>

      {createOpen ? (
        <RouteGroupForm open={createOpen} onClose={() => setCreateOpen(false)} initial={null} />
      ) : null}
    </ErrorBoundary>
  );
}

function DashboardGroupRow({ group }: { group: RouteGroup }) {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [downloading, setDownloading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const progressQuery = useQuery({
    queryKey: ["route-group-progress", group.id],
    queryFn: () => getRouteGroupProgress(group.id),
    refetchInterval: 30_000,
  });

  const progress = progressQuery.data;
  const coverage = progress ? Math.min(progress.coverage_percent, 100) : 0;
  const routeLabel = `${group.origins[0] ?? "-"}->${group.destinations[0] ?? "-"}`;
  const tripType =
    group.trip_type === "multi_city"
      ? "Multi City"
      : group.trip_type === "round_trip"
        ? "Round Trip"
        : "One Way";

  async function handleDownload(event: MouseEvent) {
    event.stopPropagation();
    setDownloading(true);

    try {
      const blob = await downloadExport(group.id);
      saveBlobAsFile(blob, `${group.name.replace(/[^a-z0-9_-]/gi, "_")}.xlsx`);
      showToast("Excel downloaded", "success");
    } catch (err) {
      showToast(getErrorMessage(err, "Download failed"), "error");
    } finally {
      setDownloading(false);
    }
  }

  async function handleTrigger(event: MouseEvent) {
    event.stopPropagation();
    setTriggering(true);

    try {
      await triggerGroupCollection(group.id);
      showToast("Collection triggered successfully", "success");
    } catch (err) {
      showToast(getErrorMessage(err, "Failed to trigger collection"), "error");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <tr
      onClick={() => navigate(`/route-groups/${group.id}`)}
      className="cursor-pointer border-b border-slate-100 transition hover:bg-slate-50"
    >
      <td className="px-4 py-3">
        <div className="font-semibold text-slate-900">{group.name}</div>
        <div className="text-xs text-slate-400">{group.destination_label}</div>
      </td>
      <td className="px-4 py-3">
        <span className="rounded-md bg-slate-100 px-2 py-1 font-mono text-xs font-semibold text-slate-700">
          {routeLabel}
        </span>
      </td>
      <td className="px-4 py-3">
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-brand-700">
          {tripType}
        </span>
      </td>
      <td className="min-w-[140px] px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-indigo-100">
            <div
              className={`h-full rounded-full ${coverage > 90 ? "bg-brand-600" : "bg-amber-500"}`}
              style={{ width: `${coverage}%` }}
            />
          </div>
          <span className="w-11 text-right text-xs font-semibold text-slate-600">
            {progress ? `${progress.coverage_percent.toFixed(0)}%` : "-"}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">{group.days_ahead}d</td>
      <td className="px-4 py-3">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
          {group.currency}
        </span>
      </td>
      <td className="px-4 py-3">
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            group.is_active ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
          }`}
        >
          {group.is_active ? "Active" : "Paused"}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex gap-2" onClick={(event) => event.stopPropagation()}>
          <button
            type="button"
            onClick={handleTrigger}
            disabled={triggering}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
            title="Trigger scrape"
          >
            <RefreshCw className={`h-4 w-4 ${triggering ? "animate-spin" : ""}`} />
          </button>
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
            title="Download export"
          >
            <Download className="h-4 w-4" />
          </button>
        </div>
      </td>
    </tr>
  );
}

function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h2 className="text-[15px] font-semibold text-slate-900">{title}</h2>
      {subtitle ? <p className="text-sm text-slate-500">{subtitle}</p> : null}
    </div>
  );
}

function HeaderPill({
  children,
  icon,
  tone,
}: {
  children: ReactNode;
  icon: ReactNode;
  tone: "green" | "slate";
}) {
  const styles =
    tone === "green"
      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
      : "border-slate-200 bg-slate-50 text-slate-600";

  return (
    <div className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium ${styles}`}>
      {icon}
      <span>{children}</span>
    </div>
  );
}

function Banner({
  tone,
  icon,
  title,
  text,
}: {
  tone: "amber" | "blue";
  icon: ReactNode;
  title: string;
  text: ReactNode;
}) {
  const styles =
    tone === "amber"
      ? "border-amber-200 bg-amber-50 text-amber-800"
      : "border-blue-200 bg-blue-50 text-blue-800";

  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${styles}`}>
      <div className="mt-0.5 shrink-0">{icon}</div>
      <div>
        <p className="font-semibold">{title}</p>
        <p className="mt-0.5 opacity-90">{text}</p>
      </div>
    </div>
  );
}
