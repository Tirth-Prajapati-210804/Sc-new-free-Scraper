import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, MapPin, RefreshCw } from "lucide-react";
import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { triggerGroupCollection } from "../api/collection";
import { getErrorMessage } from "../api/client";
import {
  downloadExport,
  getRouteGroupProgress,
  saveBlobAsFile,
} from "../api/route-groups";
import { useToast } from "../context/ToastContext";
import type { RouteGroup } from "../types/route-group";
import { formatNumber } from "../utils/format";

import { Card } from "./ui/Card";
import { Skeleton } from "./ui/Skeleton";

interface RouteGroupCardProps {
  group: RouteGroup;
}

export function RouteGroupCard({ group }: RouteGroupCardProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { showToast } = useToast();

  const [downloading, setDownloading] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const progressQuery = useQuery({
    queryKey: ["route-group-progress", group.id],
    queryFn: () => getRouteGroupProgress(group.id),
    refetchInterval: 10_000,
  });

  const progress = progressQuery.data;
  const tripType =
    group.trip_type === "round_trip"
      ? "Round Trip"
      : group.trip_type === "multi_city"
        ? "Multi City"
        : "One Way";
  const stayLabel =
    group.trip_type === "multi_city"
      ? `${group.nights} nights`
      : group.trip_type === "round_trip"
        ? `${group.nights} nights`
        : "-";
  const routeLabel = `${group.origins[0] ?? "-"}->${group.destinations[0] ?? "-"}`;
  const coveragePct = progress ? Math.min(progress.coverage_percent, 100) : 0;
  const coverageTone = coveragePct > 90 ? "bg-brand-600" : "bg-amber-500";

  async function handleDownload() {
    setDownloading(true);

    try {
      const blob = await downloadExport(group.id);
      const safeName = group.name.replace(/[^a-z0-9_-]/gi, "_");
      saveBlobAsFile(blob, `${safeName}.xlsx`);
      showToast("Excel downloaded", "success");
    } catch (err) {
      showToast(getErrorMessage(err, "Download failed"), "error");
    } finally {
      setDownloading(false);
    }
  }

  async function handleTrigger() {
    setTriggering(true);

    try {
      await triggerGroupCollection(group.id);
      showToast("Collection started. Progress will update shortly.", "success");
      await qc.invalidateQueries({ queryKey: ["collection-status"] });
      await qc.invalidateQueries({ queryKey: ["route-group-progress", group.id] });
    } catch (err) {
      showToast(getErrorMessage(err, "Failed to trigger collection"), "error");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <Card
      className="cursor-pointer p-[18px] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_18px_45px_-28px_rgba(79,70,229,0.28)]"
      onClick={() => navigate(`/route-groups/${group.id}`)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-slate-900">{group.name}</h3>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <StatusBadge active={group.is_active} />
            <Badge tone="blue">{tripType}</Badge>
            <Badge tone="slate">{group.currency}</Badge>
          </div>
        </div>

        <div className="flex gap-1.5" onClick={(event) => event.stopPropagation()}>
          <IconButton
            title="Trigger scrape"
            onClick={handleTrigger}
            spinning={triggering}
            icon={<RefreshCw className="h-4 w-4" />}
          />
          <IconButton
            title="Download export"
            onClick={handleDownload}
            disabled={downloading}
            icon={<Download className="h-4 w-4" />}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2 text-sm text-slate-400">
        <MapPin className="h-4 w-4 shrink-0" />
        <span className="truncate">{group.destination_label}</span>
        <span>|</span>
        <span className="rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-600">
          {routeLabel}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <MiniStat label="Origins" value={String(group.origins.length)} />
        <MiniStat label="Stay" value={stayLabel} />
        <MiniStat label="Window" value={`${group.days_ahead}d`} />
      </div>

      <div className="mt-5">
        {progressQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-2 w-full rounded-full" />
            <Skeleton className="h-4 w-36 rounded-md" />
          </div>
        ) : progress ? (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">
                {formatNumber(progress.dates_with_data)} / {formatNumber(progress.total_dates)} scanned
              </span>
              <span className={`font-semibold ${coveragePct > 90 ? "text-emerald-600" : "text-amber-600"}`}>
                {progress.coverage_percent.toFixed(1)}%
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-indigo-100">
              <div className={`h-full rounded-full ${coverageTone}`} style={{ width: `${coveragePct}%` }} />
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">No collection yet</span>
              <span className="font-semibold text-slate-400">0%</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-indigo-100">
              <div className="h-full w-0 rounded-full bg-brand-600" />
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function Badge({
  children,
  tone,
}: {
  children: ReactNode;
  tone: "blue" | "slate";
}) {
  const styles =
    tone === "blue"
      ? "border-blue-100 bg-blue-50 text-blue-700"
      : "border-slate-200 bg-slate-100 text-slate-600";

  return (
    <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${styles}`}>
      {children}
    </span>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium ${
        active ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-emerald-500" : "bg-amber-500"}`} />
      {active ? "Active" : "Paused"}
    </span>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-medium text-slate-400">{label}</p>
      <p className="mt-1 text-[13px] font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function IconButton({
  title,
  onClick,
  icon,
  disabled,
  spinning = false,
}: {
  title: string;
  onClick: () => void;
  icon: ReactNode;
  disabled?: boolean;
  spinning?: boolean;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50 disabled:opacity-50"
    >
      <span className={spinning ? "animate-spin" : ""}>{icon}</span>
    </button>
  );
}
