import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/api/client";

/**
 * Login dialog.
 *
 * Credentials go straight to the backend, which verifies a scrypt hash held in
 * Secrets Manager and returns a signed, expiring session token. Nothing is
 * checked in the browser — a client-side gate would ship the password in the
 * JS bundle and leave the API open.
 */
export function LoginForm({ onClose }: { onClose: () => void }) {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const firstField = useRef<HTMLInputElement>(null);

  useEffect(() => {
    firstField.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      // No navigation needed — AuthProvider sets the token and Landing
      // redirects on the next render.
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That username and password combination is not recognised."
          : err instanceof ApiError
            ? err.message
            : "Could not sign in.",
      );
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6
                 bg-canvas/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="login-title"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="floats w-full max-w-sm p-8">
        <div className="flex items-baseline justify-between mb-8">
          <h2 id="login-title" className="t-h1">
            Sign in
          </h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="t-body text-ink-faint hover:text-ink leading-none"
          >
            ×
          </button>
        </div>

        <form onSubmit={submit} className="flex flex-col gap-6">
          <label className="flex flex-col gap-1.5">
            <span className="t-label">Username</span>
            <input
              ref={firstField}
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
              className="t-body bg-transparent border-b border-rule focus:border-accent
                         outline-none py-1.5 rounded-sm"
            />
          </label>

          <label className="flex flex-col gap-1.5">
            <span className="t-label">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="t-body bg-transparent border-b border-rule focus:border-accent
                         outline-none py-1.5 rounded-sm"
            />
          </label>

          {/* aria-live so a screen reader announces the failure */}
          {error && (
            <p className="t-small text-negative" role="alert" aria-live="polite">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy || !username || !password}
            className="mt-2 py-2 t-body font-medium rounded-sm bg-ink text-canvas
                       hover:bg-accent transition-colors
                       disabled:bg-rule disabled:text-ink-faint disabled:cursor-not-allowed"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
