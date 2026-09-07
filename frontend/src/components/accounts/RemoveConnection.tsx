import { useState } from "react";
import { api, ApiError } from "@/api/client";
import type { RemoveResult } from "@/api/client";
import { clearApiCache } from "@/hooks/useApi";

/**
 * Disconnect an institution and delete its data.
 *
 * Two-step by design. This is destructive and cannot be undone from the UI: it
 * disconnects at Plaid and deletes every curated transaction and transfer group
 * belonging to the institution. The confirmation names the scope, so nobody
 * discovers what went only after it is gone.
 */
export function RemoveConnection({
  itemId,
  institutionName,
  accountCount,
  onRemoved,
}: {
  itemId: string;
  institutionName: string;
  accountCount: number;
  onRemoved: () => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RemoveResult | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      const removed = await api.removeConnection(itemId);
      // Transactions and accounts were deleted; nothing cached is still true.
      clearApiCache();
      setResult(removed);
      onRemoved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove the connection.");
    } finally {
      setBusy(false);
    }
  }

  if (result) {
    return (
      <span className="t-small text-ink-faint">
        Removed {result.accounts_removed} accounts, {result.transactions_removed} transactions
      </span>
    );
  }

  if (!confirming) {
    return (
      <button
        onClick={() => setConfirming(true)}
        className="t-small text-ink-muted hover:text-negative transition-colors"
      >
        Remove
      </button>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1.5 max-w-sm">
      <p className="t-small text-ink-muted text-right">
        Disconnect {institutionName} and delete {accountCount}{" "}
        {accountCount === 1 ? "account" : "accounts"} with all their transactions?
      </p>
      {error && (
        <p className="t-small text-negative" role="alert">
          {error}
        </p>
      )}
      <div className="flex gap-3">
        <button
          onClick={remove}
          disabled={busy}
          className="t-small text-negative hover:underline disabled:text-ink-faint"
        >
          {busy ? "Removing…" : "Yes, remove"}
        </button>
        <button
          onClick={() => setConfirming(false)}
          disabled={busy}
          className="t-small text-ink-muted hover:underline"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
