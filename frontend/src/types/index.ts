/**
 * Domain types — mirror `backend/src/ledgerly/models/`.
 * Keep these in sync with the Python dataclasses; they are the API contract.
 *
 * Money crosses the wire as a STRING, never a JS number. `0.1 + 0.2 !== 0.3`
 * in IEEE-754, and financial sums must be exact. Parse for display only.
 */

export type TransactionType =
  | "INCOME"
  | "EXPENSE"
  | "TRANSFER"
  | "REFUND"
  | "ADJUSTMENT"
  | "UNKNOWN";

export type TransactionStatus = "PENDING" | "POSTED" | "REMOVED";

export type AccountType = "depository" | "credit" | "loan" | "investment" | "other";

export type TransferKind =
  | "INTERNAL_TRANSFER"
  | "CREDIT_CARD_PAYMENT"
  | "LOAN_PAYMENT"
  | "UNKNOWN";

export type TransferStatus = "CONFIRMED" | "SUGGESTED" | "REJECTED";

export interface Transaction {
  transaction_id: string;
  account_id: string;
  item_id: string;

  transaction_date: string; // ISO date, no timezone
  authorized_date: string | null;

  /** Negative = money left the account. Positive = money entered it. */
  amount: string;
  iso_currency_code: string;

  description: string;
  merchant_name: string | null;
  normalized_merchant: string | null;

  category: string | null;
  subcategory: string | null;
  plaid_category_primary: string | null;

  transaction_type: TransactionType;
  status: TransactionStatus;
  is_pending: boolean;

  is_transfer: boolean;
  transfer_group_id: string | null;
  is_recurring: boolean;

  user_category_override: boolean;
  user_note: string | null;
}

export interface Account {
  account_id: string;
  item_id: string;
  institution_name: string | null;
  name: string;
  mask: string | null;
  account_type: AccountType;
  account_subtype: string | null;
  current_balance: string | null;
  available_balance: string | null;
  credit_limit: string | null;
  iso_currency_code: string;
  last_synced_at: string | null;
  is_liability: boolean;
}

export interface TransferGroup {
  transfer_group_id: string;
  source_transaction_id: string;
  source_account_id: string;
  destination_transaction_id: string;
  destination_account_id: string;
  amount: string; // absolute value, always positive
  transfer_kind: TransferKind;
  status: TransferStatus;
  confidence: string;
  date_gap_days: number;
}

/** A ledger entry is either a lone transaction or a matched transfer pair.
 *  The pair is the signature UI pattern (DESIGN.md §3.7A). */
export type LedgerEntry =
  | { kind: "transaction"; transaction: Transaction }
  | {
      kind: "transfer";
      group: TransferGroup;
      source: Transaction;
      destination: Transaction;
    };

export interface CategorySpend {
  category: string;
  amount: string;
  transaction_count: number;
}

export interface MonthlyCashFlow {
  month: string; // YYYY-MM
  income: string;
  expenses: string;
  net: string;
}

/* ── Reports ───────────────────────────────────────────────────────────────
   Mirrors `backend/src/ledgerly/analytics/reports.py`. */

/** The only three meanings color is allowed to carry in a report (DESIGN.md
 *  §3.2). Categories are never distinguished by hue — only by label. */
export type FlowKind = "income" | "expense" | "net";

export interface SankeyNode {
  id: string;
  label: string;
  /** Money as a string. Parsed for LAYOUT GEOMETRY only, never arithmetic. */
  value: string;
  kind: FlowKind;
  /** 0 = income sources, 1 = the single Income node, 2 = destinations. */
  column: number;
}

export interface SankeyLink {
  /** Node ids, not indices. */
  source: string;
  target: string;
  value: string;
  kind: FlowKind;
}

export interface SankeyData {
  nodes: SankeyNode[];
  links: SankeyLink[];
}

export interface CashFlowReport {
  date_from: string;
  date_to: string;
  total_income: string;
  total_expenses: string;
  net_income: string;
  /** Percentage, already ×100 by the backend. Not money — no currency symbol.
   *  NULL when the ratio is not meaningful — no income to divide by, or
   *  spending so far past income that the percentage is noise rather than a
   *  figure. Render an em dash, never a zero: 0% means "kept nothing", which
   *  is a different claim from "there is no rate to state". */
  savings_rate: string | null;
  sankey: SankeyData;
}

export interface DashboardSummary {
  net_worth: string;
  net_worth_change_month: string;
  net_worth_series: { date: string; value: string }[];
  month_income: string;
  month_spending: string;
  month_net: string;
  cash_flow: MonthlyCashFlow[];
  spending_by_category: CategorySpend[];
  /** Computed-at timestamp. Surfaced in the UI — never show stale numbers
   *  silently (DESIGN.md §3.8). */
  computed_at: string;
}
