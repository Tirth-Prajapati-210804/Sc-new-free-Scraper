import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Pencil, RefreshCw, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { triggerGroupCollection } from "../api/collection";
import { getErrorMessage } from "../api/client";
import { fetchPrices, fetchPriceTrend } from "../api/prices";
import {
  deleteRouteGroup,
  downloadExport,
  getRouteGroup,
  getRouteGroupProgress,
  saveBlobAsFile,
} from "../api/route-groups";
import { DateCoverageGrid } from "../components/DateCoverageGrid";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PriceChart } from "../components/PriceChart";
import { PriceTable } from "../components/PriceTable";
import { RouteGroupForm } from "../components/RouteGroupForm";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../context/ToastContext";
import type { DailyPrice } from "../types/price";
import { formatFreshnessLabel } from "../utils/format";
import { usePageTitle } from "../utils/usePageTitle";

function formatStopsLabel(v: number | null): string {
  if (v == null) return "Any";
  if (v === 0) return "Direct only";
  if (v === 1) return "Up to 1 stop";
  if (v === 2) return "Up to 2 stops";
  if (v === 3) return "Prefer 1 stop (fallback)";
  return String(v);
}

export function RouteGroupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { showToast } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [confirmTrigger, setConfirmTrigger] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [selectedOrigin, setSelectedOrigin] = useState<string>("");
  const [allPrices, setAllPrices] = useState<DailyPrice[]>([]);
  const [pricesLoading, setPricesLoading] = useState(false);
  const [priceHasMore, setPriceHasMore] = useState(false);
  const priceOffsetRef = useRef(0);
  const PRICE_PAGE = 100;

  const groupQuery = useQuery({
    queryKey: ["route-group", id],
    queryFn: () => getRouteGroup(id!),
    enabled: !!id,
  });

  const progressQuery = useQuery({
    queryKey: ["route-group-progress", id],
    queryFn: () => getRouteGroupProgress(id!),
    enabled: !!id,
    refetchInterval: 10_000,
  });

  const group = groupQuery.data;
  const activeOrigin = selectedOrigin || group?.origins[0] || "";
  const originForQuery = activeOrigin;
  const destForQuery = group?.destinations[0] || "";
  const returnOrigin = group?.trip_type === "multi_city" ? (group.special_sheets[0]?.origin ?? null) : null;

  const trendQuery = useQuery({
    queryKey: ["price-trend", id, originForQuery, destForQuery],
    queryFn: () =>
      fetchPriceTrend({ origin: originForQuery, destination: destForQuery, route_group_id: id }),
    enabled: !!originForQuery && !!destForQuery,
  });

  const loadPrices = useCallback(async (origin: string, newOffset: number) => {
    if (!id) return;
    setPricesLoading(true);
    try {
      const data = await fetchPrices({
        route_group_id: id,
        origin: origin || undefined,
        limit: PRICE_PAGE,
        offset: newOffset,
      });
      setAllPrices((prev) => (newOffset === 0 ? data : [...prev, ...data]));
      setPriceHasMore(data.length === PRICE_PAGE);
      priceOffsetRef.current = newOffset;
    } finally {
      setPricesLoading(false);
    }
  }, [id]);

  const priceOriginRef = useRef("");

  useEffect(() => {
    if (!group?.origins.length) return;
    if (!selectedOrigin || !group.origins.includes(selectedOrigin)) {
      setSelectedOrigin(group.origins[0]);
    }
  }, [group?.origins, selectedOrigin]);

  useEffect(() => {
    if (!id || !group?.origins.length || !activeOrigin) return;
    if (priceOriginRef.current === activeOrigin) return;

    priceOriginRef.current = activeOrigin;
    setAllPrices([]);
    void loadPrices(activeOrigin, 0);
  }, [activeOrigin, group?.origins, id, loadPrices]);

  const handlePriceLoadMore = useCallback(
    () => loadPrices(activeOrigin, priceOffsetRef.current + PRICE_PAGE),
    [PRICE_PAGE, activeOrigin, loadPrices],
  );

  usePageTitle(group?.name ?? "Route Group");

  async function handleDownload() {
    if (!group) return;
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

  async function handleTrigger() {
    if (!id) return;
    setConfirmTrigger(false);
    setTriggering(true);
    try {
      await triggerGroupCollection(id);
      showToast("Collection triggered successfully", "success");
      qc.invalidateQueries({ queryKey: ["collection-status"] });
      qc.invalidateQueries({ queryKey: ["route-group-progress", id] });
    } catch (err) {
      showToast(getErrorMessage(err, "Failed to trigger collection"), "error");
    } finally {
      setTriggering(false);
    }
  }

  if (groupQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
    );
  }

  if (!group) {
    return (
      <div className="py-16 text-center text-slate-400">
        Route group not found.{" "}
        <Link to="/" className="text-brand-600 hover:underline">
          Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link
            to="/"
            className="flex items-center gap-1.5 text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Dashboard
          </Link>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button variant="secondary" onClick={() => setEditOpen(true)}>
              <Pencil className="h-4 w-4" />
              Edit
            </Button>
            <Button variant="secondary" onClick={() => setConfirmTrigger(true)} loading={triggering}>
              <RefreshCw className="h-4 w-4" />
              Trigger Scrape
            </Button>
            <Button variant="primary" onClick={handleDownload} loading={downloading}>
              <Download className="h-4 w-4" />
              Download Excel
            </Button>
            <button
              onClick={() => setConfirmDelete(true)}
              aria-label="Delete route group"
              title="Delete route group"
              className="rounded-lg border border-red-200 px-3 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        <Card className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-1">
              <h2 className="text-2xl font-bold text-slate-950">{group.name}</h2>
              <p className="text-sm text-slate-500">{group.destination_label}</p>
              <p className="text-xs font-medium text-slate-400">
                {formatFreshnessLabel(progressQuery.data?.last_scraped_at ?? null)}
              </p>
            </div>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                group.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"
              }`}
            >
              {group.is_active ? "Active" : "Inactive"}
            </span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Nights</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">{group.nights}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Days Ahead</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">{group.days_ahead}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Currency</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">{group.currency}</p>
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-slate-400">Stops</p>
              <p className="mt-0.5 text-sm font-semibold text-slate-800">{formatStopsLabel(group.max_stops)}</p>
            </div>
          </div>

          <div className={`mt-5 grid gap-4 border-t border-slate-100 pt-5 ${group.trip_type === "multi_city" ? "lg:grid-cols-2" : ""}`}>
            <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
              <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">Outbound</p>
              <div className="flex flex-wrap items-center gap-2">
                {group.origins.map((code) => (
                  <span
                    key={`origin-${code}`}
                    className="rounded-md border border-brand-200 bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700"
                  >
                    {code}
                  </span>
                ))}
                <span className="text-slate-300">→</span>
                {group.destinations.map((code) => (
                  <span
                    key={`destination-${code}`}
                    className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700"
                  >
                    {code}
                  </span>
                ))}
              </div>
            </div>

            {group.trip_type === "multi_city" && returnOrigin ? (
              <div className="rounded-2xl border border-slate-100 bg-slate-50/70 p-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-400">Return</p>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700">
                    {returnOrigin}
                  </span>
                  <span className="text-slate-300">→</span>
                  {group.origins.map((code) => (
                    <span
                      key={`return-${code}`}
                      className="rounded-md border border-brand-200 bg-brand-50 px-2 py-0.5 text-xs font-semibold text-brand-700"
                    >
                      {code}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        </Card>

        <Card className="p-6">
          <h3 className="mb-4 text-[15px] font-semibold text-slate-900">Collection Progress</h3>
          {progressQuery.isLoading ? (
            <Skeleton className="h-32" />
          ) : progressQuery.isError ? (
            <p className="text-sm text-red-500">Failed to load progress. Try refreshing the page.</p>
          ) : progressQuery.data ? (
            <DateCoverageGrid progress={progressQuery.data} />
          ) : (
            <p className="text-sm text-slate-400">No data collected yet. Trigger a collection to start.</p>
          )}
        </Card>

        <Card className="p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
            <h3 className="text-[15px] font-semibold text-slate-900">Price Trend</h3>
            <div className="flex items-center gap-2 text-sm">
              <select
                aria-label="Select origin"
                value={selectedOrigin || group.origins[0]}
                onChange={(e) => setSelectedOrigin(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-sm font-medium text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                {group.origins.map((origin) => (
                  <option key={origin} value={origin}>
                    {origin}
                  </option>
                ))}
              </select>
              <span className="text-slate-400">→</span>
              <span className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-sm font-medium text-slate-700">
                {destForQuery}
              </span>
            </div>
          </div>
          {trendQuery.isLoading ? (
            <Skeleton className="h-64" />
          ) : trendQuery.isError ? (
            <p className="py-8 text-center text-sm text-red-500">Failed to load price trend data.</p>
          ) : (trendQuery.data ?? []).length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">
              No price data yet for this route. Trigger a collection first.
            </p>
          ) : (
            <PriceChart data={trendQuery.data ?? []} />
          )}
        </Card>

        <Card className="overflow-hidden p-0">
          <div className="flex flex-wrap items-center justify-between gap-4 px-6 pt-6">
            <div>
              <h3 className="text-[15px] font-semibold text-slate-900">Price Data</h3>
              {group.trip_type === "multi_city" && returnOrigin ? (
                <p className="mt-1 text-xs text-slate-400">
                  Each row is one full itinerary fare for {group.origins[0]} → {group.destinations[0]} and{" "}
                  {returnOrigin} → {group.origins[0]} after {group.nights} nights.
                </p>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <select
                aria-label="Filter by origin"
                value={selectedOrigin}
                onChange={(e) => setSelectedOrigin(e.target.value)}
                className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">All origins</option>
                {group.origins.map((origin) => (
                  <option key={origin} value={origin}>
                    {origin}
                  </option>
                ))}
              </select>
              {allPrices.length > 0 ? (
                <span className="text-xs text-slate-400">
                  {allPrices.length} rows{priceHasMore ? "+" : ""}
                </span>
              ) : null}
            </div>
          </div>
          <PriceTable
            prices={allPrices}
            isLoading={pricesLoading && allPrices.length === 0}
            hasMore={priceHasMore}
            onLoadMore={handlePriceLoadMore}
            loadingMore={pricesLoading && allPrices.length > 0}
            groupCurrency={group.currency}
            tripType={group.trip_type}
            nights={group.nights}
            returnOrigin={returnOrigin}
          />
        </Card>

        {editOpen ? (
          <RouteGroupForm open={editOpen} onClose={() => setEditOpen(false)} initial={group} />
        ) : null}

        {confirmTrigger ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="mx-4 w-full max-w-sm rounded-[24px] bg-white p-6 shadow-xl">
              <h3 className="text-base font-semibold text-slate-900">Trigger Full Scrape?</h3>
              <p className="mt-2 text-sm text-slate-500">
                This will start a collection run for missing dates in{" "}
                <span className="font-medium">{group.name}</span>.
              </p>
              <div className="mt-5 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setConfirmTrigger(false)}>
                  Cancel
                </Button>
                <Button variant="primary" onClick={handleTrigger} loading={triggering}>
                  Yes, trigger
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        {confirmDelete ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="mx-4 w-full max-w-sm rounded-[24px] bg-white p-6 shadow-xl">
              <h3 className="text-base font-semibold text-slate-900">Delete Route Group</h3>
              <p className="mt-2 text-sm text-slate-500">
                Are you sure you want to delete{" "}
                <span className="font-medium text-slate-700">{group.name}</span>? All collected price data will be permanently lost.
              </p>
              <div className="mt-5 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
                <button
                  onClick={async () => {
                    setDeleting(true);
                    try {
                      await deleteRouteGroup(id!);
                      await qc.invalidateQueries({ queryKey: ["route-groups"] });
                      showToast("Route group deleted", "success");
                      navigate("/", { replace: true });
                    } catch (err) {
                      showToast(getErrorMessage(err, "Failed to delete route group"), "error");
                      setDeleting(false);
                      setConfirmDelete(false);
                    }
                  }}
                  disabled={deleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Delete"}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </ErrorBoundary>
  );
}
