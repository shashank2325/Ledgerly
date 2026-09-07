import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { api, ApiError } from "@/api/client";
import { clearApiCache } from "@/hooks/useApi";

/**
 * Plaid Link entry point.
 *
 * The browser only ever holds a link_token and a public_token — both
 * short-lived, neither a credential for the user's bank. The permanent access
 * token is minted and stored entirely server-side and never crosses this
 * boundary (SPEC §11, ADR 0004).
 */
export function ConnectButton({ onConnected }: { onConnected?: () => void }) {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<{ name: string; token: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .createLinkToken()
      .then((r) => setLinkToken(r.link_token))
      .catch((e: ApiError) => setStatus(e.message));
  }, []);

  const exchange = useCallback(
    async (publicToken: string, force = false) => {
      setBusy(true);
      setStatus(null);
      try {
        const result = await api.exchangePublicToken(publicToken, force);
        // Accounts, balances and the dashboard all just changed.
        clearApiCache();
        setDuplicate(null);
        setStatus(
          `Connected ${result.institution_name ?? "institution"} — ${result.accounts_added} accounts`,
        );
        onConnected?.();
      } catch (error) {
        if (error instanceof ApiError && error.code === "institution_already_connected") {
          // Not a dead end — a second login at the same bank is legitimate.
          // Ask, rather than silently duplicating every account.
          setDuplicate({
            name: String(error.detail?.institution_name ?? "this institution"),
            token: publicToken,
          });
        } else {
          setStatus(error instanceof ApiError ? error.message : "Connection failed");
        }
      } finally {
        setBusy(false);
      }
    },
    [onConnected],
  );

  const { open, ready } = usePlaidLink({
    token: linkToken,
    // Plaid types public_token as nullable — a null here means Link reported
    // success without completing the handoff. Exchanging null would surface as
    // an opaque 400, so treat it as a failed connection instead.
    onSuccess: (publicToken) => {
      if (publicToken) void exchange(publicToken);
      else setStatus("Link finished without returning a token. Please try again.");
    },
    onExit: (err) => err && setStatus(err.display_message ?? err.error_message ?? null),
  });

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        onClick={() => open()}
        disabled={!ready || !linkToken || busy}
        className="t-small text-accent hover:underline disabled:text-ink-faint
                   disabled:no-underline disabled:cursor-not-allowed"
      >
        {busy ? "Connecting…" : "Connect account"}
      </button>

      {duplicate && (
        <div className="text-right max-w-xs">
          <p className="t-small text-ink-muted">
            {duplicate.name} is already connected. Add a second login?
          </p>
          <div className="flex gap-3 justify-end mt-1">
            <button onClick={() => void exchange(duplicate.token, true)}
              className="t-small text-accent hover:underline">Add anyway</button>
            <button onClick={() => setDuplicate(null)}
              className="t-small text-ink-muted hover:underline">Cancel</button>
          </div>
        </div>
      )}

      {status && <p className="t-small text-ink-faint text-right max-w-xs">{status}</p>}
    </div>
  );
}
