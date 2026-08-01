import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

const STORAGE_KEY = "dk:admin-session";

function readToken(): string | null {
  try {
    return window.sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeToken(token: string | null): void {
  try {
    if (token) window.sessionStorage.setItem(STORAGE_KEY, token);
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // The in-memory state still works when storage is blocked.
  }
}

export function useAdminSession() {
  const [token, setToken] = useState<string | null>(() => readToken());
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking] = useState(() => token !== null);

  const invalidate = useCallback(() => {
    storeToken(null);
    setToken(null);
    setAuthenticated(false);
    setChecking(false);
  }, []);

  useEffect(() => {
    if (!token) {
      setChecking(false);
      setAuthenticated(false);
      return;
    }
    let active = true;
    setChecking(true);
    api.adminSession(token)
      .then(() => {
        if (active) setAuthenticated(true);
      })
      .catch(() => {
        if (active) invalidate();
      })
      .finally(() => {
        if (active) setChecking(false);
      });
    return () => {
      active = false;
    };
  }, [token, invalidate]);

  const login = useCallback(async (password: string) => {
    const session = await api.adminLogin(password);
    storeToken(session.token);
    setToken(session.token);
    setAuthenticated(true);
    setChecking(false);
  }, []);

  const logout = useCallback(async () => {
    if (token) await api.adminLogout(token).catch(() => void 0);
    invalidate();
  }, [token, invalidate]);

  return { token, authenticated, checking, login, logout, invalidate };
}
