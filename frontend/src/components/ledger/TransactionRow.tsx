import { Money } from "@/components/ui/Money";
import { formatDate } from "@/utils/date";
import type { Transaction } from "@/types";

/** Shared column grid. Every ledger row — lone or paired — uses this so
 *  amounts stay aligned down the whole column. */
/**
 * Shared column grid so amounts align down the whole column.
 *
 * Below md the five columns cannot fit — they need ~560px — so the row becomes
 * two lines: merchant and amount on the first, then date, category and account
 * on the second. Squeezing five columns onto a phone would truncate the
 * merchant name, which is the field you actually scan by.
 */
export const LEDGER_GRID =
  "grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5 " +
  "md:grid-cols-[68px_minmax(0,1fr)_130px_150px_110px] md:items-center md:gap-4";

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
      className={`${LEDGER_GRID} w-full text-left row-hover px-1 rule-b
        py-2.5 md:py-0 md:h-10 md:flex-none ${selected ? "bg-accent/[0.06]" : ""}`}
    >
      {/* Date leads on desktop; on mobile it moves to the second line, where it
          sits with the other secondary fields. */}
      <span className="hidden md:block t-num-sm text-ink-muted">
        {formatDate(txn.transaction_date)}
      </span>

      <span className="flex items-center gap-2 min-w-0 order-1 md:order-none">
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

      {/* Amount stays on the first line on mobile: it is the second thing you
          look for after the merchant, and pushing it down would make every row
          require two glances. */}
      <span className="text-right order-2 md:order-none">
        <Money amount={txn.amount} type={txn.transaction_type} pending={txn.is_pending} />
      </span>

      {/* Second line on mobile, columns three and four on desktop. */}
      <span
        className="order-3 md:order-none col-span-2 md:col-span-1 flex items-baseline gap-2
                   md:gap-0 min-w-0"
      >
        <span className="md:hidden t-num-sm text-ink-faint shrink-0">
          {formatDate(txn.transaction_date)}
        </span>
        <span className="t-small text-ink-muted truncate">
          {txn.category ?? <span className="text-ink-faint">Uncategorized</span>}
        </span>
        <span className="md:hidden t-small text-ink-faint truncate ml-auto">
          {accountName ?? txn.account_id}
        </span>
      </span>

      <span className="hidden md:block t-small text-ink-faint truncate">
        {accountName ?? txn.account_id}
      </span>
    </button>
  );
}
