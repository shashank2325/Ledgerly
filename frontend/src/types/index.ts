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
