import type {
  RouteGroup,
  RouteGroupFromTextCreate,
  RouteGroupFromTextResponse,
  RouteGroupProgress,
} from "../types/route-group";
import { api } from "./client";

export async function listRouteGroups(): Promise<RouteGroup[]> {
  const res = await api.get<RouteGroup[]>("/api/v1/route-groups/?active_only=false");
  return res.data;
}

export async function getRouteGroup(id: string): Promise<RouteGroup> {
  const res = await api.get<RouteGroup>(`/api/v1/route-groups/${id}`);
  return res.data;
}

export async function createRouteGroup(
  data: Partial<RouteGroup>,
): Promise<RouteGroup> {
  const res = await api.post<RouteGroup>("/api/v1/route-groups/", data);
  return res.data;
}

export async function createRouteGroupFromText(
  data: RouteGroupFromTextCreate,
): Promise<RouteGroupFromTextResponse> {
  const res = await api.post<RouteGroupFromTextResponse>(
    "/api/v1/route-groups/from-text",
    data,
  );
  return res.data;
}

export async function updateRouteGroup(
  id: string,
  data: Partial<RouteGroup>,
): Promise<RouteGroup> {
  const res = await api.put<RouteGroup>(`/api/v1/route-groups/${id}`, data);
  return res.data;
}

export async function deleteRouteGroup(id: string): Promise<void> {
  await api.delete(`/api/v1/route-groups/${id}`);
}

export async function getRouteGroupProgress(
  id: string,
): Promise<RouteGroupProgress> {
  const res = await api.get<RouteGroupProgress>(
    `/api/v1/route-groups/${id}/progress`,
  );
  return res.data;
}

// Excel download — returns Blob
export async function downloadExport(id: string): Promise<Blob> {
  const res = await api.get(`/api/v1/route-groups/${id}/export`, {
    responseType: "blob",
  });
  return res.data;
}

// Trigger download in browser
export function saveBlobAsFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
