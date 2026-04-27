import type { CollectionRun, ScrapeLogEntry } from "../types/price";
import { api } from "./client";

export interface CollectionProgress {
  routes_total: number;
  routes_done: number;
  routes_failed: number;
  prices_total: number;
  prices_started: number;
  prices_done: number;
  prices_failed: number;
  dates_scraped: number;
  current_origin: string;
  current_destination: string;
  current_date: string;
}

export interface CollectionStatus {
  is_collecting: boolean;
  scheduler_running: boolean;
  progress?: CollectionProgress;
}

export async function getCollectionStatus(): Promise<CollectionStatus> {
  const res = await api.get<CollectionStatus>("/api/v1/collection/status");
  return res.data;
}

export async function triggerCollection(): Promise<{ status: string }> {
  const res = await api.post<{ status: string }>("/api/v1/collection/trigger");
  return res.data;
}

export async function stopCollection(): Promise<{ status: string }> {
  const res = await api.post<{ status: string }>("/api/v1/collection/stop");
  return res.data;
}

export async function triggerGroupCollection(groupId: string): Promise<void> {
  await api.post(`/api/v1/collection/trigger-group/${groupId}`);
}

export async function triggerGroupCollectionDate(groupId: string, date: string): Promise<void> {
  await api.post(`/api/v1/collection/trigger-group/${groupId}/date/${date}`);
}

export async function fetchCollectionRuns(limit = 20): Promise<CollectionRun[]> {
  const res = await api.get<CollectionRun[]>("/api/v1/collection/runs", {
    params: { limit },
  });
  return res.data;
}

export async function fetchScrapeLogs(params: {
  route_group_id?: string;
  origin?: string;
  limit?: number;
}): Promise<ScrapeLogEntry[]> {
  const res = await api.get<ScrapeLogEntry[]>("/api/v1/collection/logs", {
    params,
  });
  return res.data;
}
