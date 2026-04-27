import type { HealthResponse, OverviewStats } from "../types/stats";
import { api } from "./client";

export async function fetchOverviewStats(): Promise<OverviewStats> {
  const res = await api.get<OverviewStats>("/api/v1/stats/overview");
  return res.data;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await api.get<HealthResponse>("/health");
  return res.data;
}
