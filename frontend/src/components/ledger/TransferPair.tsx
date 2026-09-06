import { useState } from "react";
import { Money } from "@/components/ui/Money";
import { formatDate } from "@/utils/date";
import { LEDGER_GRID } from "./TransactionRow";
import type { Transaction, TransferGroup } from "@/types";

/**
 * THE SIGNATURE PATTERN — DESIGN.md §3.7A.
 *
 * Every competing product stores a transfer as a category label on ONE
 * transaction, which is why they double-count (Monarch's own docs concede it).
 * A transfer is a RELATIONSHIP between two transactions, so we render it as
 * one: both legs, visibly joined, money visibly moving between accounts.
 *
 * The user does not have to trust that the transfer was excluded from
 * spending — they can see the pair cancel.
 *
 * CONFIRMED pairs get a solid violet rule. SUGGESTED pairs get a dashed rule
 * and confirm/reject controls — we never silently remove money from the
 * reports on a guess.
 */
export function TransferPair({
  group,
  source,
  destination,
  sourceAccountName,
  destAccountName,
  onConfirm,
  onReject,
}: {
  group: TransferGroup;
  source: Transaction;
  destination: Transaction;
  sourceAccountName?: string;
  destAccountName?: string;
  onConfirm?: (id: string) => void;
  onReject?: (id: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const suggested = group.status === "SUGGESTED";

  const kindLabel =
    group.transfer_kind === "CREDIT_CARD_PAYMENT"
      ? "Card payment"
      : group.transfer_kind === "LOAN_PAYMENT"
        ? "Loan payment"
        : "Transfer";

  return (
    <div
      className={`border-l-2 ${
        suggested ? "border-l-transfer/40 border-dashed" : "border-l-transfer"
      } pl-2`}
    >
      {/* Collapsed summary — one line, the default view. */}
      <div className={`${LEDGER_GRID} row row-hover px-1`}>
        <span className="t-num-sm text-ink-muted">{formatDate(source.transaction_date)}</span>

        <button
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-2 min-w-0 text-left"
          aria-expanded={expanded}
        >
          <span className="t-body text-transfer">{kindLabel}</span>
          <span className="t-small text-ink-muted truncate">
            {sourceAccountName ?? source.account_id}
            <span className="text-transfer mx-1.5" aria-label="to">
              →
            </span>
            {destAccountName ?? destination.account_id}
          </span>
          <span className="t-small text-ink-faint shrink-0" aria-hidden="true">
            {expanded ? "▾" : "▸"}
          </span>
        </button>

        <span className="t-small text-ink-muted">
          {suggested ? (
            <span className="text-transfer">Suggested</span>
          ) : (
            /* Both legs cancel — state it plainly. This is the whole point. */
            <span className="text-ink-faint">Not counted</span>
          )}
        </span>

        <span className="t-small text-ink-faint">
          {group.date_gap_days > 0 && `${group.date_gap_days}d apart`}
        </span>

        <span className="text-right">
          <Money amount={group.amount} type="TRANSFER" />
        </span>
      </div>

      {/* Expanded — both legs, so the cancellation is literally visible. */}
      {expanded && (
        <div className="bg-transfer/[0.03]">
          {[
            { txn: source, name: sourceAccountName, role: "From" },
            { txn: destination, name: destAccountName, role: "To" },
          ].map(({ txn, name, role }) => (
            <div key={txn.transaction_id} className={`${LEDGER_GRID} row px-1 border-b-0`}>
              <span className="t-num-sm text-ink-faint">{formatDate(txn.transaction_date)}</span>
              <span className="t-small text-ink-muted truncate pl-3">
                <span className="t-label mr-2">{role}</span>
                {txn.description}
              </span>
              <span />
              <span className="t-small text-ink-faint truncate">{name ?? txn.account_id}</span>
              <span className="text-right">
                {/* forceSign is essential here: without it both legs read as
                    "$2,000.00" and the cancellation — the whole point of the
                    pair — is invisible. */}
                <Money amount={txn.amount} size="sm" forceSign />
              </span>
            </div>
          ))}
          {/* Spell out the arithmetic. This is the claim the product makes. */}
          <div className={`${LEDGER_GRID} px-1 py-1.5`}>
            <span />
            <span className="t-small text-ink-faint pl-3">Net effect on spending</span>
            <span />
            <span />
            <span className="t-num-sm text-ink-faint text-right">$0.00</span>
          </div>
        </div>
      )}

      {/* Suggested pairs need a human decision before they affect any total. */}
      {suggested && (
        <div className="flex items-center gap-3 py-2 px-1 rule-b">
          <span className="t-small text-ink-muted">
            Looks like a transfer ({Math.round(Number(group.confidence) * 100)}% confidence)
          </span>
          <button
            onClick={() => onConfirm?.(group.transfer_group_id)}
            className="t-small text-transfer underline underline-offset-2 hover:no-underline"
          >
            Confirm
          </button>
          <button
            onClick={() => onReject?.(group.transfer_group_id)}
            className="t-small text-ink-muted underline underline-offset-2 hover:no-underline"
          >
            Not a transfer
          </button>
        </div>
      )}
    </div>
  );
}
