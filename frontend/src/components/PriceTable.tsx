import { useMemo, useState } from "react";

import type { DailyPrice } from "../types/price";
import type { TripType } from "../types/route-group";
import { formatRelativeTime } from "../utils/format";
import { Button } from "./ui/Button";
import { Skeleton } from "./ui/Skeleton";

interface Column {
  key: keyof DailyPrice;
  label: string;
  align?: "left" | "right";
}

const BASE_COLUMNS: Column[] = [
  { key: "depart_date", label: "Date" },
  { key: "origin", label: "Origin" },
  { key: "destination", label: "Destination" },
  { key: "airline", label: "Airline" },
  { key: "stops", label: "Stops" },
  { key: "duration_minutes", label: "Duration" },
  { key: "price", label: "Price", align: "right" },
  { key: "provider", label: "Provider" },
  { key: "scraped_at", label: "Scraped At" },
];

interface PriceTableProps {
  prices: DailyPrice[];
  isLoading: boolean;
  hasMore?: boolean;
  onLoadMore?: () => void;
  loadingMore?: boolean;
  groupCurrency?: string;
  tripType?: TripType;
  nights?: number;
  returnOrigin?: string | null;
}

function addDays(rawDate: string, days: number): string {
  const value = new Date(`${rawDate}T00:00:00`);
  value.setDate(value.getDate() + days);
  return value.toISOString().slice(0, 10);
}

function HeaderCell({
  column,
  sortDir,
  sortKey,
  onToggleSort,
}: {
  column: Column;
  sortDir: "asc" | "desc";
  sortKey: keyof DailyPrice;
  onToggleSort: (key: keyof DailyPrice) => void;
}) {
  return (
    <th
      className={`cursor-pointer select-none px-6 py-3 hover:text-slate-700 ${
        column.align === "right" ? "text-right" : ""
      }`}
      onClick={() => onToggleSort(column.key)}
    >
      {column.label} {sortKey === column.key ? (sortDir === "asc" ? "↑" : "↓") : ""}
    </th>
  );
}

function FragmentWithMultiCityHeaders({
  column,
  isMultiCity,
  sortDir,
  sortKey,
  onToggleSort,
}: {
  column: Column;
  isMultiCity: boolean;
  sortDir: "asc" | "desc";
  sortKey: keyof DailyPrice;
  onToggleSort: (key: keyof DailyPrice) => void;
}) {
  return (
    <>
      <HeaderCell
        column={column}
        sortDir={sortDir}
        sortKey={sortKey}
        onToggleSort={onToggleSort}
      />
      {isMultiCity && column.key === "destination" ? <th className="px-6 py-3">Return From</th> : null}
      {isMultiCity && column.key === "destination" ? <th className="px-6 py-3">Return Date</th> : null}
    </>
  );
}

export function PriceTable({
  prices,
  isLoading,
  hasMore,
  onLoadMore,
  loadingMore,
  groupCurrency,
  tripType,
  nights = 0,
  returnOrigin,
}: PriceTableProps) {
  const [sortKey, setSortKey] = useState<keyof DailyPrice>("depart_date");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const isMultiCity = tripType === "multi_city";
  const columns = useMemo(() => {
    if (!isMultiCity) {
      return BASE_COLUMNS;
    }

    return BASE_COLUMNS.map((column) => {
      if (column.key === "destination") {
        return { ...column, label: "Outbound To" };
      }
      if (column.key === "price") {
        return { ...column, label: "Total Fare" };
      }
      return column;
    });
  }, [isMultiCity]);

  function toggleSort(key: keyof DailyPrice) {
    if (sortKey === key) {
      setSortDir((dir) => (dir === "asc" ? "desc" : "asc"));
      return;
    }

    setSortKey(key);
    setSortDir("asc");
  }

  const sorted = useMemo(() => {
    return [...prices].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];

      if (av == null) return 1;
      if (bv == null) return -1;

      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [prices, sortDir, sortKey]);

  if (isLoading) {
    return <Skeleton className="h-64 rounded-xl" />;
  }

  if (!prices.length) {
    return (
      <p className="py-10 text-center text-sm text-slate-400">
        No prices found. Run a collection to populate data.
      </p>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-y border-slate-200 bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
              {columns.map((col) => (
                <FragmentWithMultiCityHeaders
                  key={col.key}
                  column={col}
                  isMultiCity={isMultiCity}
                  sortDir={sortDir}
                  sortKey={sortKey}
                  onToggleSort={toggleSort}
                />
              ))}
            </tr>
          </thead>

          <tbody>
            {sorted.map((price, i) => (
              <tr
                key={price.id}
                className={`transition-colors hover:bg-brand-50/40 ${
                  i % 2 !== 0 ? "bg-slate-50/50" : ""
                }`}
              >
                <td className="px-6 py-3 text-slate-700">{price.depart_date}</td>
                <td className="px-6 py-3 font-medium text-slate-800">
                  <span className="rounded-md bg-indigo-50 px-2 py-1 font-mono text-xs font-semibold text-brand-700">
                    {price.origin}
                  </span>
                </td>
                <td className="px-6 py-3 text-slate-700">
                  <span className="rounded-md bg-emerald-50 px-2 py-1 font-mono text-xs font-semibold text-emerald-700">
                    {price.destination}
                  </span>
                </td>
                {isMultiCity ? (
                  <td className="px-6 py-3 text-slate-700">
                    <span className="rounded-md bg-amber-50 px-2 py-1 font-mono text-xs font-semibold text-amber-700">
                      {returnOrigin || "-"}
                    </span>
                  </td>
                ) : null}
                {isMultiCity ? (
                  <td className="px-6 py-3 text-slate-700">{addDays(price.depart_date, nights)}</td>
                ) : null}
                <td className="px-6 py-3 text-slate-700">{price.airline}</td>
                <td className="px-6 py-3 text-slate-700">
                  {price.stops == null ? (
                    "-"
                  ) : price.stops === 0 ? (
                    <span className="font-medium text-green-600">Direct</span>
                  ) : (
                    `${price.stops} stop${price.stops > 1 ? "s" : ""}`
                  )}
                </td>
                <td className="px-6 py-3 text-slate-700">
                  {price.duration_minutes == null
                    ? "-"
                    : `${Math.floor(price.duration_minutes / 60)}h ${price.duration_minutes % 60}m`}
                </td>
                <td className="px-6 py-3 text-right font-medium text-slate-900">
                  {Math.round(price.price).toLocaleString()}{" "}
                  <span className="text-xs text-slate-400">
                    {groupCurrency ?? price.currency}
                  </span>
                </td>
                <td className="px-6 py-3 capitalize text-slate-500">{price.provider}</td>
                <td className="px-6 py-3 text-slate-400">
                  {formatRelativeTime(price.scraped_at)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hasMore ? (
        <div className="border-t border-slate-100 px-6 py-4">
          <Button variant="secondary" onClick={onLoadMore} loading={loadingMore}>
            Load more
          </Button>
        </div>
      ) : null}
    </>
  );
}
