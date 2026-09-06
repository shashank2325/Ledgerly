/**
 * Mock fixtures for Phase 1. Replaced by the real API in Phase 5.
 *
 * These numbers RECONCILE deliberately — category totals sum to the month's
 * spending, and net worth equals assets minus liabilities. Ledgerly's thesis is
 * financial correctness, so fixtures that did not add up would be a bad
 * foundation to design against.
 *
 * The important demonstration: $4,000 of transfers (savings, card payment,
 * brokerage) appear in the ledger but in NEITHER income nor spending.
 */

import type {
  Account,
  DashboardSummary,
  LedgerEntry,
  Transaction,
  TransferGroup,
} from "@/types";

export const mockAccounts: Account[] = [
  {
    account_id: "acc_checking",
    item_id: "item_chase",
    institution_name: "Chase",
    name: "Total Checking",
    mask: "4821",
    account_type: "depository",
    account_subtype: "checking",
    current_balance: "8432.19",
    available_balance: "8432.19",
    credit_limit: null,
    iso_currency_code: "USD",
    last_synced_at: new Date(Date.now() - 32 * 60_000).toISOString(),
    is_liability: false,
  },
  {
    account_id: "acc_savings",
    item_id: "item_ally",
    institution_name: "Ally Bank",
    name: "Online Savings",
    mask: "9013",
    account_type: "depository",
    account_subtype: "savings",
    current_balance: "24150.00",
    available_balance: "24150.00",
    credit_limit: null,
    iso_currency_code: "USD",
    last_synced_at: new Date(Date.now() - 32 * 60_000).toISOString(),
    is_liability: false,
  },
  {
    account_id: "acc_card",
    item_id: "item_chase",
    institution_name: "Chase",
    name: "Sapphire Reserve",
    mask: "7742",
    account_type: "credit",
    account_subtype: "credit card",
    current_balance: "1847.32",
    available_balance: null,
    credit_limit: "15000.00",
    iso_currency_code: "USD",
    last_synced_at: new Date(Date.now() - 32 * 60_000).toISOString(),
    is_liability: true,
  },
  {
    account_id: "acc_brokerage",
    item_id: "item_fidelity",
    institution_name: "Fidelity",
    name: "Individual Brokerage",
    mask: "2288",
    account_type: "investment",
    account_subtype: "brokerage",
    current_balance: "67204.88",
    available_balance: null,
    credit_limit: null,
    iso_currency_code: "USD",
    last_synced_at: new Date(Date.now() - 6 * 3600_000).toISOString(),
    is_liability: false,
  },
  {
    account_id: "acc_loan",
    item_id: "item_navient",
    institution_name: "Navient",
    name: "Student Loan",
    mask: "5510",
    account_type: "loan",
    account_subtype: "student",
    current_balance: "12400.00",
    available_balance: null,
    credit_limit: null,
    iso_currency_code: "USD",
    last_synced_at: new Date(Date.now() - 26 * 3600_000).toISOString(),
    is_liability: true,
  },
];

export const accountName = (id: string): string => {
  const a = mockAccounts.find((x) => x.account_id === id);
  return a ? `${a.name} ··${a.mask}` : id;
};

function txn(t: Partial<Transaction> & Pick<Transaction, "transaction_id" | "account_id" | "transaction_date" | "amount">): Transaction {
  return {
    item_id: "item_chase",
    authorized_date: null,
    iso_currency_code: "USD",
    description: "",
    merchant_name: null,
    normalized_merchant: null,
    category: null,
    subcategory: null,
    plaid_category_primary: null,
    transaction_type: "EXPENSE",
    status: "POSTED",
    is_pending: false,
    is_transfer: false,
    transfer_group_id: null,
    is_recurring: false,
    user_category_override: false,
    user_note: null,
    ...t,
  };
}

// ── September 2026, month to date ────────────────────────────────────────────
// Income 7,500.00 · Spending 2,836.00 · Transfers 4,000.00 (excluded from both)

export const mockTransactions: Transaction[] = [
  txn({ transaction_id: "t_salary", account_id: "acc_checking", transaction_date: "2026-09-01",
        amount: "7500.00", description: "ACME CORP DIRECT DEP", normalized_merchant: "Acme Corp",
        category: "Income", subcategory: "Salary", transaction_type: "INCOME", is_recurring: true }),
  txn({ transaction_id: "t_rent", account_id: "acc_checking", transaction_date: "2026-09-01",
        amount: "-2400.00", description: "OAKWOOD PROPERTIES", normalized_merchant: "Oakwood Properties",
        category: "Housing", subcategory: "Rent", is_recurring: true }),
  txn({ transaction_id: "t_wf", account_id: "acc_card", transaction_date: "2026-09-02",
        amount: "-142.30", description: "WHOLEFDS MKT #10234", normalized_merchant: "Whole Foods",
        category: "Food", subcategory: "Groceries" }),
  txn({ transaction_id: "t_sbux", account_id: "acc_card", transaction_date: "2026-09-02",
        amount: "-6.75", description: "STARBUCKS STORE 8841", normalized_merchant: "Starbucks",
        category: "Food", subcategory: "Coffee" }),
  txn({ transaction_id: "t_amzn", account_id: "acc_card", transaction_date: "2026-09-03",
        amount: "-84.99", description: "AMZN Mktp US*2K4LP", normalized_merchant: "Amazon",
        category: "Shopping", subcategory: "General" }),
  txn({ transaction_id: "t_shell", account_id: "acc_card", transaction_date: "2026-09-03",
        amount: "-52.40", description: "SHELL OIL 57442310", normalized_merchant: "Shell",
        category: "Transportation", subcategory: "Gas" }),
  txn({ transaction_id: "t_nflx", account_id: "acc_card", transaction_date: "2026-09-04",
        amount: "-22.99", description: "NETFLIX.COM", normalized_merchant: "Netflix",
        category: "Subscriptions", subcategory: "Streaming", is_recurring: true }),
  txn({ transaction_id: "t_chip", account_id: "acc_card", transaction_date: "2026-09-05",
        amount: "-14.85", description: "CHIPOTLE 2241", normalized_merchant: "Chipotle",
        category: "Food", subcategory: "Restaurants" }),
  txn({ transaction_id: "t_uber", account_id: "acc_card", transaction_date: "2026-09-05",
        amount: "-23.60", description: "UBER *TRIP", normalized_merchant: "Uber",
        category: "Transportation", subcategory: "Rideshare" }),
  txn({ transaction_id: "t_tj", account_id: "acc_card", transaction_date: "2026-09-06",
        amount: "-88.12", description: "TRADER JOE'S #445", normalized_merchant: "Trader Joe's",
        category: "Food", subcategory: "Groceries", is_pending: true, status: "PENDING" }),

  // ── Transfer legs. Note transaction_type TRANSFER — these are excluded from
  //    both income and spending totals. This is the whole thesis. ────────────
  txn({ transaction_id: "t_sav_out", account_id: "acc_checking", transaction_date: "2026-09-02",
        amount: "-2000.00", description: "ONLINE TRANSFER TO ALLY", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_savings" }),
  txn({ transaction_id: "t_sav_in", account_id: "acc_savings", transaction_date: "2026-09-03",
        amount: "2000.00", description: "TRANSFER FROM CHASE 4821", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_savings" }),
  txn({ transaction_id: "t_card_out", account_id: "acc_checking", transaction_date: "2026-09-04",
        amount: "-1500.00", description: "CHASE CREDIT CRD AUTOPAY", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_card" }),
  txn({ transaction_id: "t_card_in", account_id: "acc_card", transaction_date: "2026-09-04",
        amount: "1500.00", description: "PAYMENT THANK YOU", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_card" }),
  txn({ transaction_id: "t_brk_out", account_id: "acc_checking", transaction_date: "2026-09-05",
        amount: "-500.00", description: "FIDELITY TRANSFER", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_brokerage" }),
  txn({ transaction_id: "t_brk_in", account_id: "acc_brokerage", transaction_date: "2026-09-06",
        amount: "500.00", description: "ACH DEPOSIT", transaction_type: "TRANSFER",
        is_transfer: true, transfer_group_id: "tg_brokerage" }),
];

export const mockTransferGroups: TransferGroup[] = [
  { transfer_group_id: "tg_savings", source_transaction_id: "t_sav_out",
    source_account_id: "acc_checking", destination_transaction_id: "t_sav_in",
    destination_account_id: "acc_savings", amount: "2000.00",
    transfer_kind: "INTERNAL_TRANSFER", status: "CONFIRMED", confidence: "0.98", date_gap_days: 1 },
  { transfer_group_id: "tg_card", source_transaction_id: "t_card_out",
    source_account_id: "acc_checking", destination_transaction_id: "t_card_in",
    destination_account_id: "acc_card", amount: "1500.00",
    transfer_kind: "CREDIT_CARD_PAYMENT", status: "CONFIRMED", confidence: "0.99", date_gap_days: 0 },
  // Deliberately SUGGESTED — exercises the confirm/reject affordance.
  { transfer_group_id: "tg_brokerage", source_transaction_id: "t_brk_out",
    source_account_id: "acc_checking", destination_transaction_id: "t_brk_in",
    destination_account_id: "acc_brokerage", amount: "500.00",
    transfer_kind: "INTERNAL_TRANSFER", status: "SUGGESTED", confidence: "0.82", date_gap_days: 1 },
];

/** Collapse raw transactions into ledger entries, pairing transfer legs.
 *  In production this shaping happens server-side; here it mirrors what the
 *  API will return. */
export function buildLedger(
  transactions: Transaction[],
  groups: TransferGroup[],
): LedgerEntry[] {
  const byId = new Map(transactions.map((t) => [t.transaction_id, t]));
  const consumed = new Set<string>();
  const entries: LedgerEntry[] = [];

  for (const g of groups) {
    const source = byId.get(g.source_transaction_id);
    const destination = byId.get(g.destination_transaction_id);
    // A group missing a leg is a data-quality failure. Skip it rather than
    // rendering half a transfer — the legs then show as ordinary rows.
    if (!source || !destination) continue;
    consumed.add(g.source_transaction_id);
    consumed.add(g.destination_transaction_id);
    entries.push({ kind: "transfer", group: g, source, destination });
  }

  for (const t of transactions) {
    if (consumed.has(t.transaction_id)) continue;
    entries.push({ kind: "transaction", transaction: t });
  }

  return entries.sort((a, b) => {
    const da = a.kind === "transfer" ? a.source.transaction_date : a.transaction.transaction_date;
    const db = b.kind === "transfer" ? b.source.transaction_date : b.transaction.transaction_date;
    return db.localeCompare(da);
  });
}

export const mockDashboard: DashboardSummary = {
  // 8432.19 + 24150.00 + 67204.88 − 1847.32 − 12400.00 = 85539.75
  net_worth: "85539.75",
  net_worth_change_month: "4664.00",
  net_worth_series: [
    { date: "2025-10", value: "71200.00" }, { date: "2025-11", value: "72840.00" },
    { date: "2025-12", value: "70115.00" }, { date: "2026-01", value: "73990.00" },
    { date: "2026-02", value: "75420.00" }, { date: "2026-03", value: "74880.00" },
    { date: "2026-04", value: "77650.00" }, { date: "2026-05", value: "79310.00" },
    { date: "2026-06", value: "78200.00" }, { date: "2026-07", value: "81440.00" },
    { date: "2026-08", value: "80875.75" }, { date: "2026-09", value: "85539.75" },
  ],
  month_income: "7500.00",
  month_spending: "2836.00",
  month_net: "4664.00",
  cash_flow: [
    { month: "2026-04", income: "7500.00", expenses: "-5210.44", net: "2289.56" },
    { month: "2026-05", income: "7500.00", expenses: "-4880.19", net: "2619.81" },
    { month: "2026-06", income: "7500.00", expenses: "-6120.77", net: "1379.23" },
    { month: "2026-07", income: "8250.00", expenses: "-5044.10", net: "3205.90" },
    { month: "2026-08", income: "7500.00", expenses: "-5933.62", net: "1566.38" },
    { month: "2026-09", income: "7500.00", expenses: "-2836.00", net: "4664.00" },
  ],
  // Sums to 2836.00 — identical to month_spending, by construction.
  spending_by_category: [
    { category: "Housing", amount: "-2400.00", transaction_count: 1 },
    { category: "Food", amount: "-252.02", transaction_count: 4 },
    { category: "Shopping", amount: "-84.99", transaction_count: 1 },
    { category: "Transportation", amount: "-76.00", transaction_count: 2 },
    { category: "Subscriptions", amount: "-22.99", transaction_count: 1 },
  ],
  computed_at: new Date(Date.now() - 32 * 60_000).toISOString(),
};
