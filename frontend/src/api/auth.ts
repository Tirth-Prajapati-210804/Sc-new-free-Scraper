import type { TokenResponse, User } from "../types/auth";
import { api } from "./client";

export async function login(
  email: string,
  password: string,
): Promise<TokenResponse> {
  // Backend expects JSON body: { email, password }
  const res = await api.post<TokenResponse>("/api/v1/auth/login", {
    email,
    password,
  });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await api.get<User>("/api/v1/auth/me");
  return res.data;
}
