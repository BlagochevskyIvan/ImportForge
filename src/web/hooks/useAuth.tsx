"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import {
  ApiError, clearSession, describeError, login as apiLogin, logout as apiLogout,
  restoreSession, SESSION_CHANNEL, SESSION_ENDED, SESSION_SOURCE, type Credentials, type User,
} from "@/lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
  retry: () => Promise<void>;
  login: (data: Credentials) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const retry = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setUser(await restoreSession()); }
    catch (cause) {
      if (!(cause instanceof ApiError && cause.status === 401)) setError(describeError(cause));
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    let active = true;
    const ended = () => { setUser(null); setError(null); };
    window.addEventListener(SESSION_ENDED, ended);
    const channel = typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel(SESSION_CHANNEL);
    if (channel) channel.onmessage = (event) => {
      if (event.data?.source === SESSION_SOURCE) return;
      if (event.data?.type === "logout") clearSession();
      if (event.data?.type === "login") {
        // Another tab may have switched accounts; discard the previous profile/list.
        clearSession();
        void retry();
      }
    };
    restoreSession().then((profile) => { if (active) setUser(profile); }).catch((cause) => {
      if (active && !(cause instanceof ApiError && cause.status === 401)) setError(describeError(cause));
    }).finally(() => { if (active) setLoading(false); });
    return () => {
      active = false;
      window.removeEventListener(SESSION_ENDED, ended);
      channel?.close();
    };
  }, [retry]);

  async function login(data: Credentials) {
    const profile = await apiLogin(data);
    setError(null);
    setUser(profile);
  }

  async function logout() {
    // A network failure is not a confirmed server logout: keep the error visible.
    await apiLogout();
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, error, retry, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
