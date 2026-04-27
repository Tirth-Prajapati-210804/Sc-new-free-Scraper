import { api } from "./client";

export interface UserRecord {
  id: string;
  full_name: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface UserCreatePayload {
  full_name: string;
  email: string;
  password: string;
  role: string;
}

export interface UserUpdatePayload {
  full_name?: string;
  email?: string;
  password?: string;
  role?: string;
  is_active?: boolean;
}

export async function listUsers(): Promise<UserRecord[]> {
  const res = await api.get<UserRecord[]>("/api/v1/users/");
  return res.data;
}

export async function createUser(data: UserCreatePayload): Promise<UserRecord> {
  const res = await api.post<UserRecord>("/api/v1/users/", data);
  return res.data;
}

export async function updateUser(id: string, data: UserUpdatePayload): Promise<UserRecord> {
  const res = await api.put<UserRecord>(`/api/v1/users/${id}`, data);
  return res.data;
}

export async function deleteUser(id: string): Promise<void> {
  await api.delete(`/api/v1/users/${id}`);
}
