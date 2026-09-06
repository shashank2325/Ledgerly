import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, setAuthToken } from "@/api/client";

/**
 * Session state.
 *
 * The token is a server-signed, expiring bearer credential — the browser cannot
 * forge or extend one. It is stored in localStorage so a refresh does not log
 * you out; that is readable by any script on the origin, which is an accepted
 * trade for a single-user app with a strict CSP and no third-party scripts.
 * A Cognito-backed httpOnly cookie replaces this in Phase 9.
 */

interface AuthState {
  token: string | null;
  username: string | null;
  ready: boolean; // false until the stored token has been validated
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const KEY = "ledgerly-session";
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(KEY));
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  // Keep the api client's header in sync with state, so no call site has to
  // remember to attach the token.
  useEffect(() => {
    setAuthToken(token);
  }, [token]);

  // Validate a stored token once on boot. Without this, an expired token would
  // render the app shell and then fail every request — showing a wall of errors
  // instead of a login screen.
  useEffect(() => {
    if (!token) {
      setReady(true);
      return;
    }
    let cancelled = false;
    api
      .getSession()
      .then((r) => !cancelled && setUsername(r.username))
      .catch(() => {
        if (cancelled) return;
        localStorage.removeItem(KEY);
        setToken(null);
      })
      .finally(() => !cancelled && setReady(true));
    return () => {
      cancelled = true;
    };
    // Runs once: re-validating on every token change would loop after login.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (user: string, password: string) => {
    const result = await api.login(user, password);
    localStorage.setItem(KEY, result.token);
    setToken(result.token);
    setUsername(result.username);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(KEY);
    setToken(null);
    setUsername(null);
  }, []);

  const value = useMemo(
    () => ({ token, username, ready, login, logout }),
    [token, username, ready, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
