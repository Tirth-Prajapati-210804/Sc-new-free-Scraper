import { useQuery } from "@tanstack/react-query";
import { Download, Search, SlidersHorizontal } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

import type { DailyPrice } from "../types/price";
import { fetchPriceTrend, fetchPrices } from "../api/prices";
import { getErrorMessage } from "../api/client";
import { listRouteGroups } from "../api/route-groups";
import { DateRangeInput } from "../components/ui/DateRangeInput";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { ErrorBoundary } from "../components/ErrorBoundary";
import { PriceChart } from "../components/PriceChart";
import { PriceTable } from "../components/PriceTable";
import { useToast } from "../context/ToastContext";
import { usePageTitle } from "../utils/usePageTitle";

interface Filters {
  route_group_id: string;
  origin: string;
  date_from: string;
  date_to: string;
}

const EMPTY_FILTERS: Filters = {
  route_group_id: "",
  origin: "",
  date_from: "",
  date_to: "",
};

const PAGE_SIZE = 100;

function exportCsv(rows: DailyPrice[]) {
  const header = "Date,Origin,Destination,Airline,Price,Currency,Stops,Duration(min),Provider\n";
  const lines = rows.map((row) =>
    [
      row.depart_date,
      row.origin,
      row.destination,
      row.airline,
      row.price,
      row.currency ?? "",
      row.stops ?? "",
      row.duration_minutes ?? "",
      row.provider,
    ].join(","),
  );

  const blob = new Blob([header + lines.join("\n")], { type: "text/csv" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "prices.csv";
  link.click();
  URL.revokeObjectURL(link.href);
}

export function DataExplorerPage() {
  usePageTitle("Data Explorer");

  const { showToast } = useToast();
  const [pending, setPending] = useState<Filters>(EMPTY_FILTERS);
  const [applied, setApplied] = useState<Filters>(EMPTY_FILTERS);
  const [allPrices, setAllPrices] = useState<DailyPrice[]>([]);
  const [pricesLoading, setPricesLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const offsetRef = useRef(0);

  const [airlineFilter, setAirlineFilter] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");

  const groupsQuery = useQuery({
    queryKey: ["route-groups"],
    queryFn: listRouteGroups,
  });

  const selectedGroup = groupsQuery.data?.find((group) => group.id === pending.route_group_id);

  function handleGroupChange(id: string) {
    setPending({ ...EMPTY_FILTERS, route_group_id: id });
  }

  const loadPrices = useCallback(
    async (filters: Filters, newOffset: number) => {
      if (!filters.route_group_id) return;

      setPricesLoading(true);
      try {
        const data = await fetchPrices({
          route_group_id: filters.route_group_id,
          origin: filters.origin || undefined,
          date_from: filters.date_from || undefined,
          date_to: filters.date_to || undefined,
          limit: PAGE_SIZE,
          offset: newOffset,
        });

        setAllPrices((prev) => (newOffset === 0 ? data : [...prev, ...data]));
        setHasMore(data.length === PAGE_SIZE);
        offsetRef.current = newOffset;
      } catch (err) {
        setHasMore(false);
        showToast(getErrorMessage(err, "Failed to load prices"), "error");
      } finally {
        setPricesLoading(false);
      }
    },
    [showToast],
  );

  function handleApply() {
    const next = { ...pending };
    setApplied(next);
    setAllPrices([]);
    setAirlineFilter("");
    setMinPrice("");
    setMaxPrice("");
    void loadPrices(next, 0);
  }

  const handleLoadMore = useCallback(() => {
    void loadPrices(applied, offsetRef.current + PAGE_SIZE);
  }, [applied, loadPrices]);

  const appliedGroup = groupsQuery.data?.find((group) => group.id === applied.route_group_id);
  const trendOrigin = applied.origin || appliedGroup?.origins[0] || "";
  const trendDest = appliedGroup?.destinations[0] || "";

  const trendQuery = useQuery({
    queryKey: ["explorer-trend", applied, trendOrigin, trendDest],
    queryFn: () =>
      fetchPriceTrend({
        origin: trendOrigin,
        destination: trendDest,
        date_from: applied.date_from || undefined,
        date_to: applied.date_to || undefined,
      }),
    enabled: !!trendOrigin && !!trendDest,
  });

  const airlines = useMemo(
    () => [...new Set(allPrices.map((price) => price.airline))].filter(Boolean).sort(),
    [allPrices],
  );

  const filteredPrices = useMemo(() => {
    let rows = allPrices;
    if (airlineFilter) rows = rows.filter((price) => price.airline === airlineFilter);
    if (minPrice !== "") rows = rows.filter((price) => price.price >= Number(minPrice));
    if (maxPrice !== "") rows = rows.filter((price) => price.price <= Number(maxPrice));
    return rows;
  }, [allPrices, airlineFilter, maxPrice, minPrice]);

  return (
    <ErrorBoundary>
      <div className="space-y-6">
        <section className="rounded-[30px] border border-slate-200 bg-white px-6 py-5 shadow-[0_18px_50px_-38px_rgba(15,23,42,0.45)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Explore
          </p>
          <h1 className="mt-1 text-3xl font-bold text-slate-950">Data Explorer</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
            Choose a route group, narrow the travel window, and inspect collected price history before exporting.
          </p>

          <div className="mt-6 rounded-[24px] border border-slate-200 bg-slate-50 p-4">
            <div className="grid gap-4 xl:grid-cols-[220px_160px_minmax(0,1fr)_auto] xl:items-end">
              <Select
                label="Route Group"
                value={pending.route_group_id}
                onChange={(e) => handleGroupChange(e.target.value)}
              >
                <option value="">Select group...</option>
                {groupsQuery.data?.map((group) => (
                  <option key={group.id} value={group.id}>
                    {group.name}
                  </option>
                ))}
              </Select>

              <Select
                label="Origin"
                value={pending.origin}
                onChange={(e) => setPending((current) => ({ ...current, origin: e.target.value }))}
                disabled={!selectedGroup}
              >
                <option value="">All origins</option>
                {selectedGroup?.origins.map((origin) => (
                  <option key={origin} value={origin}>
                    {origin}
                  </option>
                ))}
              </Select>

              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Travel Window
                </p>
                <DateRangeInput
                  dateFrom={pending.date_from}
                  dateTo={pending.date_to}
                  onDateFromChange={(value) => setPending((current) => ({ ...current, date_from: value }))}
                  onDateToChange={(value) => setPending((current) => ({ ...current, date_to: value }))}
                />
              </div>

              <Button
                variant="primary"
                onClick={handleApply}
                disabled={!pending.route_group_id}
                className="h-11"
              >
                Apply
              </Button>
            </div>
          </div>
        </section>

        {!applied.route_group_id ? (
          <section className="rounded-[30px] border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
            <Search className="mx-auto h-12 w-12 text-slate-300" />
            <h2 className="mt-5 text-lg font-semibold text-slate-900">Select a route group to explore</h2>
            <p className="mt-2 text-sm text-slate-500">
              Choose a group above and click Apply to load trends and price rows.
            </p>
          </section>
        ) : (
          <>
            <Card className="p-6">
              <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Trend
                  </p>
                  <h2 className="mt-1 text-[15px] font-semibold text-slate-950">Price Trend</h2>
                </div>

                {trendOrigin && trendDest ? (
                  <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                    {trendOrigin}
                    <span className="text-slate-300">→</span>
                    {trendDest}
                  </div>
                ) : null}
              </div>

              {trendQuery.isError ? (
                <p className="py-8 text-center text-sm text-red-500">Failed to load price trend data.</p>
              ) : (
                <PriceChart data={trendQuery.data ?? []} />
              )}
            </Card>

            <Card className="overflow-hidden p-0">
              <div className="border-b border-slate-200 px-6 py-5">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Records
                    </p>
                    <h2 className="mt-1 text-[15px] font-semibold text-slate-950">Collected Prices</h2>
                    <p className="mt-1 text-sm text-slate-500">
                      Filter the loaded rows by airline or price range before exporting.
                    </p>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[180px_110px_110px_auto_auto]">
                    {airlines.length > 0 ? (
                      <Select
                        label="Airline"
                        aria-label="Filter by airline"
                        value={airlineFilter}
                        onChange={(e) => setAirlineFilter(e.target.value)}
                      >
                        <option value="">All airlines</option>
                        {airlines.map((airline) => (
                          <option key={airline} value={airline}>
                            {airline}
                          </option>
                        ))}
                      </Select>
                    ) : (
                      <div />
                    )}

                    <div>
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Min Price
                      </p>
                      <input
                        type="number"
                        aria-label="Min price"
                        placeholder="0"
                        value={minPrice}
                        onChange={(e) => setMinPrice(e.target.value)}
                        className="h-11 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-brand-500"
                      />
                    </div>

                    <div>
                      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                        Max Price
                      </p>
                      <input
                        type="number"
                        aria-label="Max price"
                        placeholder="5000"
                        value={maxPrice}
                        onChange={(e) => setMaxPrice(e.target.value)}
                        className="h-11 w-full rounded-xl border border-slate-200 bg-white px-4 text-sm outline-none transition focus:border-brand-500"
                      />
                    </div>

                    <div className="flex items-end">
                      <div className="inline-flex h-11 items-center rounded-xl border border-slate-200 bg-slate-50 px-4 text-sm text-slate-600">
                        <SlidersHorizontal className="mr-2 h-4 w-4 text-slate-400" />
                        {filteredPrices.length} row{filteredPrices.length !== 1 ? "s" : ""}
                        {hasMore && !airlineFilter && !minPrice && !maxPrice ? "+" : ""}
                      </div>
                    </div>

                    {filteredPrices.length > 0 ? (
                      <div className="flex items-end">
                        <Button variant="secondary" onClick={() => exportCsv(filteredPrices)} className="h-11">
                          <Download className="h-4 w-4" />
                          Download CSV
                        </Button>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              <PriceTable
                prices={filteredPrices}
                isLoading={pricesLoading && allPrices.length === 0}
                hasMore={hasMore && !airlineFilter && !minPrice && !maxPrice}
                onLoadMore={handleLoadMore}
                loadingMore={pricesLoading && allPrices.length > 0}
                groupCurrency={appliedGroup?.currency}
              />
            </Card>
          </>
        )}
      </div>
    </ErrorBoundary>
  );
}
