import { Money } from "@/components/ui/Money";
import { formatDate } from "@/utils/date";
import type { Transaction } from "@/types";

/** Shared column grid. Every ledger row — lone or paired — uses this so
 *  amounts stay aligned down the whole column. */
export const LEDGER_GRID =
  "grid grid-cols-[68px_minmax(0,1fr)_130px_150px_110px] items-center gap-4";

export function TransactionRow({
  txn,
  onSelect,
  selected = false,
  accountName,
}: {
  txn: Transaction;
  onSelect?: (t: Transaction) => void;
  selected?: boolean;
  accountName?: string;
}) {
  return (
    <button
      onClick={() => onSelect?.(txn)}
      aria-current={selected ? "true" : undefined}
      className={`${LEDGER_GRID} w-full text-left row row-hover px-1 ${
        selected ? "bg-accent/[0.06]" : ""
      }`}
    >
      <span className="t-num-sm text-ink-muted">{formatDate(txn.transaction_date)}</span>

      <span className="flex items-center gap-2 min-w-0">
        <span className="t-body truncate">
          {txn.normalized_merchant ?? txn.merchant_name ?? txn.description}
        </span>
        {txn.is_pending && (
          /* Pending marker: amber dot + the word, never color alone. */
          <span className="flex items-center gap-1 shrink-0">
            <span className="w-1 h-1 rounded-full bg-pending" aria-hidden="true" />
            <span className="t-small text-pending">pending</span>
          </span>
        )}
        {txn.is_recurring && (
          <span className="t-small text-ink-faint shrink-0" title="Recurring">
            ↻
          </span>
        )}
      </span>

      <span className="t-small text-ink-muted truncate">
        {txn.category ?? <span className="text-ink-faint">Uncategorized</span>}
      </span>

      <span className="t-small text-ink-faint truncate">{accountName ?? txn.account_id}</span>

      <span className="text-right">
        <Money amount={txn.amount} type={txn.transaction_type} pending={txn.is_pending} />
      </span>
    </button>
  );
}
