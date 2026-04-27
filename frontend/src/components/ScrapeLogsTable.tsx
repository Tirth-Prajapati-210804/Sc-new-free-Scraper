import {
  AlertCircle,
  Ban,
  CheckCircle2,
  FileSearch,
  KeyRound,
  MinusCircle,
  XCircle,
} from "lucide-react";

import type { ScrapeLogEntry } from "../types/price";
import { formatRelativeTime } from "../utils/format";
import { Skeleton } from "./ui/Skeleton";

interface ScrapeLogsTableProps {
  logs: ScrapeLogEntry[];
  isLoading: boolean;
}

export function ScrapeLogsTable({
  logs,
  isLoading,
}: ScrapeLogsTableProps) {
  if (isLoading) {
    return <Skeleton className="h-72 rounded-3xl" />;
  }

  if (!logs.length) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-3xl border border-dashed border-slate-200 py-10 text-center">
        <FileSearch className="h-8 w-8 text-slate-300" />
        <p className="text-sm font-semibold text-slate-700">No scrape logs found</p>
        <p className="text-xs text-slate-400">Logs appear after a collection run.</p>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[16px] border border-slate-200">
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50">
            <tr className="border-b border-slate-200">
              <Th>Time</Th>
              <Th>Route</Th>
              <Th>Provider</Th>
              <Th>Status</Th>
              <Th align="right">Price</Th>
              <Th align="right">Ms</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 bg-white">
            {logs.map((log) => (
              <tr
                key={log.id}
                className="transition-colors hover:bg-slate-50"
                title={log.error_message ?? undefined}
              >
                <Td muted>{formatRelativeTime(log.created_at)}</Td>
                <Td>
                  <span className="rounded-lg bg-slate-100 px-2 py-1 font-mono text-[11px] font-medium text-slate-700">
                    {log.origin}→{log.destination}
                  </span>
                </Td>
                <Td className="capitalize text-slate-700">{log.provider}</Td>
                <Td>
                  <StatusBadge status={log.status} />
                </Td>
                <Td align="right">
                  {log.cheapest_price != null ? (
                    <span className="font-medium text-slate-900">
                      ${Math.round(log.cheapest_price).toLocaleString()}
                    </span>
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </Td>
                <Td align="right">
                  <DurationCell ms={log.duration_ms} />
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Th({
  children,
  align = "left",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
}) {
  return (
    <th
      className={`px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500 ${
        align === "right" ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function Td({
  children,
  muted,
  align = "left",
  className = "",
}: {
  children: React.ReactNode;
  muted?: boolean;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <td
      className={`px-4 py-3 ${muted ? "text-slate-500" : ""} ${
        align === "right" ? "text-right" : "text-left"
      } ${className}`}
    >
      {children}
    </td>
  );
}

function StatusBadge({
  status,
}: {
  status: ScrapeLogEntry["status"];
}) {
  if (status === "success") {
    return (
      <Badge
        icon={<CheckCircle2 className="h-3.5 w-3.5" />}
        text="Success"
        cls="bg-emerald-50 text-emerald-700"
      />
    );
  }

  if (status === "no_results") {
    return (
      <Badge
        icon={<MinusCircle className="h-3.5 w-3.5" />}
        text="No Results"
        cls="bg-amber-50 text-amber-700"
      />
    );
  }

  if (status === "rate_limited") {
    return (
      <Badge
        icon={<AlertCircle className="h-3.5 w-3.5" />}
        text="Limited"
        cls="bg-orange-50 text-orange-700"
      />
    );
  }

  if (status === "quota_exhausted") {
    return (
      <Badge
        icon={<Ban className="h-3.5 w-3.5" />}
        text="Quota"
        cls="bg-amber-50 text-amber-700"
      />
    );
  }

  if (status === "auth_error") {
    return (
      <Badge
        icon={<KeyRound className="h-3.5 w-3.5" />}
        text="Auth Error"
        cls="bg-rose-50 text-rose-700"
      />
    );
  }

  return (
    <Badge
      icon={<XCircle className="h-3.5 w-3.5" />}
      text="Error"
      cls="bg-red-50 text-red-700"
    />
  );
}

function Badge({
  icon,
  text,
  cls,
}: {
  icon: React.ReactNode;
  text: string;
  cls: string;
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-[11px] font-medium ${cls}`}>
      {icon}
      {text}
    </span>
  );
}

function DurationCell({ ms }: { ms: number | null }) {
  if (ms == null) {
    return <span className="text-slate-400">—</span>;
  }

  const cls =
    ms < 1000
      ? "text-emerald-600"
      : ms < 5000
        ? "text-amber-600"
        : "text-red-600";

  return <span className={`font-medium ${cls}`}>{ms.toLocaleString()}</span>;
}
