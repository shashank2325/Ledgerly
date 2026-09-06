import { formatMoney, moneyToString } from "@/utils/money";
import type { TransactionType } from "@/types";

/**
 * The single way money is rendered anywhere in Ledgerly. DESIGN.md §3.4.
 *
 * Never format an amount by hand — this component owns tabular alignment, the
 * receding units, the sign convention, and the accessible label.
 */

interface MoneyProps {
  amount: string;
  currency?: string;
  type?: TransactionType;
  pending?: boolean;
  /** Show cents. True in the ledger, false in summaries. */
  exact?: boolean;
  /** Render both + and − explicitly. For the expanded transfer pair, where the
   *  two legs must visibly cancel. */
  forceSign?: boolean;
  size?: "sm" | "base" | "lg";
  className?: string;
}

const SIZE_CLASS = {
  sm: "t-num-sm",
  base: "t-num",
  lg: "t-num-lg",
} as const;

/** Color confirms the meaning; the sign carries it. Expenses are ink, not red —
 *  spending is the normal state of a ledger, not an error. */
function colorFor(type: TransactionType | undefined, pending: boolean): string {
  if (pending) return "text-pending";
  switch (type) {
    case "INCOME":
      return "text-income";
    case "TRANSFER":
      return "text-transfer";
    case "REFUND":
      return "text-income";
    default:
      return "text-ink";
  }
}

export function Money({
  amount,
  currency = "USD",
  type,
  pending = false,
  exact = true,
  forceSign = false,
  size = "base",
  className = "",
}: MoneyProps) {
  const parts = formatMoney(amount, {
    currency,
    exact,
    signed: type === "INCOME" || type === "REFUND",
    arrow: type === "TRANSFER" && !forceSign,
    forceSign,
    // Only an EXPENSE row suppresses its minus sign. Any other negative — a
    // balance, a net figure, an uncategorised amount — shows it.
    bareNegative: type === "EXPENSE",
  });

  return (
    <span
      className={`${SIZE_CLASS[size]} ${colorFor(type, pending)} ${
        pending ? "italic" : ""
      } tabular-nums whitespace-nowrap ${className}`}
      /* Screen readers get the unambiguous value, not the styled fragments. */
      aria-label={moneyToString(amount, currency)}
    >
      {parts.sign && <span aria-hidden="true">{parts.sign}</span>}
      <span className="num-unit" aria-hidden="true">
        {parts.symbol}
      </span>
      <span aria-hidden="true">{parts.whole}</span>
      {parts.fraction && (
        <span className="num-unit" aria-hidden="true">
          {parts.fraction}
        </span>
      )}
    </span>
  );
}
