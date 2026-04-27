import type { DailyPrice, PriceTrend } from "../types/price";
import { api } from "./client";

export async function fetchPrices(params: {
  route_group_id?: string;
  origin?: string;
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}): Promise<DailyPrice[]> {
  const res = await api.get<DailyPrice[]>("/api/v1/prices/", { params });
  return res.data;
}

export async function fetchPriceTrend(params: {
  origin: string;
  destination: string;
  route_group_id?: string;
  date_from?: string;
  date_to?: string;
}): Promise<PriceTrend[]> {
  const res = await api.get<Array<{ depart_date: string; price: number; airline: string }>>(
    "/api/v1/prices/trend",
    { params },
  );
  // Map backend's depart_date → date for chart component
  return res.data.map((p) => ({ date: p.depart_date, price: p.price, airline: p.airline }));
}
