/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { getMe, login as apiLogin } from "../api/auth";
import type { User } from "../types/auth";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const TOKEN_STORAGE_KEY = "token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Start as loading only if a token is present; otherwise we know immediately
  const [loading, setLoading] = useState(
    () => !!sessionStorage.getItem(TOKEN_STORAGE_KEY),
  );

  // Restore session on mount
  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_STORAGE_KEY);
    if (!token) return;
    getMe()
      .then(setUser)
      .catch(() => sessionStorage.removeItem(TOKEN_STORAGE_KEY))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const tokenRes = await apiLogin(email, password);
    sessionStorage.setItem(TOKEN_STORAGE_KEY, tokenRes.access_token);
    setUser(tokenRes.user);
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
