import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { api, setAuthToken } from "../api/client";
import type { AdjusterRead, StaffTokenResponse } from "../api/types";

const STORAGE_KEY = "adjuster-console:token";

interface AuthContextValue {
  user: AdjusterRead | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdjusterRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch {
      // localStorage unavailable -- proceed as logged out.
    }

    if (!stored) {
      setIsLoading(false);
      return;
    }

    setAuthToken(stored);
    api
      .get<AdjusterRead>("/auth/me")
      .then(setUser)
      .catch(() => {
        // Token expired/invalid -- clear it rather than staying stuck
        // sending a bad Authorization header on every request.
        setAuthToken(null);
        try {
          localStorage.removeItem(STORAGE_KEY);
        } catch {
          // ignore
        }
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const response = await api.post<StaffTokenResponse>("/auth/login", { email, password });
    setAuthToken(response.access_token);
    try {
      localStorage.setItem(STORAGE_KEY, response.access_token);
    } catch {
      // Session still works for this tab; it just won't survive a reload.
    }
    setUser(response.user);
  }

  function logout() {
    setAuthToken(null);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, isLoading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
