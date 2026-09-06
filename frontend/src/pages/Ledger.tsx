import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/primitives";
import { TransactionRow, LEDGER_GRID } from "@/components/ledger/TransactionRow";
import { TransferPair } from "@/components/ledger/TransferPair";
import { DetailPanel } from "@/components/ledger/DetailPanel";
import { accountName, buildLedger, mockAccounts, mockTransactions, mockTransferGroups } from "@/api/mock";
import type { Transaction, TransactionType } from "@/types";

const TYPE_FILTERS: { value: TransactionType | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "EXPENSE", label: "Expenses" },
  { value: "INCOME", label: "Income" },
  { value: "TRANSFER", label: "Transfers" },
];

export function Ledger() {
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [search, setSearch] = useState("");

  const typeFilter = (params.get("type") ?? "ALL") as TransactionType | "ALL";
  const categoryFilter = params.get("category");
  const accountFilter = params.get("account");

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "ALL") next.delete(key);
    else next.set(key, value);
    setParams(next);
  };

  const entries = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matches = (t: Transaction) =>
      (typeFilter === "ALL" || t.transaction_type === typeFilter) &&
      (!categoryFilter || t.category === categoryFilter) &&
      (!accountFilter || t.account_id === accountFilter) &&
      (!q ||
        t.description.toLowerCase().includes(q) ||
        (t.normalized_merchant ?? "").toLowerCase().includes(q) ||
        (t.category ?? "").toLowerCase().includes(q));

    const filtered = mockTransactions.filter(matches);
    const keep = new Set(filtered.map((t) => t.transaction_id));
    // Keep a transfer group only when at least one leg survives the filter,
    // so a pair is never rendered half-missing.
    const groups = mockTransferGroups.filter(
      (g) => keep.has(g.source_transaction_id) || keep.has(g.destination_transaction_id),
    );
    const legIds = new Set(groups.flatMap((g) => [g.source_transaction_id, g.destination_transaction_id]));
    const withLegs = mockTransactions.filter((t) => keep.has(t.transaction_id) || legIds.has(t.transaction_id));
    return buildLedger(withLegs, groups);
  }, [typeFilter, categoryFilter, accountFilter, search]);

  const categories = [...new Set(mockTransactions.map((t) => t.category).filter(Boolean))] as string[];
  const activeFilters = [categoryFilter, accountFilter].filter(Boolean).length + (typeFilter !== "ALL" ? 1 : 0);

  return (
    <div className="flex gap-0">
      <div className="flex-1 min-w-0">
        <PageHeader
          title="Ledger"
          meta={`${entries.length} ${entries.length === 1 ? "entry" : "entries"}`}
          action={
            activeFilters > 0 ? (
              <button onClick={() => { setParams(new URLSearchParams()); setSearch(""); }}
                className="t-small text-accent hover:underline">
                Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""}
              </button>
            ) : undefined
          }
        />

        {/* Sticky filter bar. Hairline underline, no chrome. */}
        <div className="sticky top-0 bg-canvas z-10 pb-3 rule-b-strong mb-1">
          <div className="flex items-center gap-4 flex-wrap">
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search"
              aria-label="Search transactions"
              className="t-body bg-transparent border-b border-rule focus:border-accent
                         outline-none py-1 w-48 placeholder:text-ink-faint"
            />

            <div className="flex gap-3" role="group" aria-label="Filter by type">
              {TYPE_FILTERS.map((f) => (
                <button
                  key={f.value}
                  onClick={() => setParam("type", f.value)}
                  aria-pressed={typeFilter === f.value}
                  className={`t-small transition-colors ${
                    typeFilter === f.value ? "text-ink font-medium" : "text-ink-muted hover:text-ink"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <select
              value={accountFilter ?? ""}
              onChange={(e) => setParam("account", e.target.value || null)}
              aria-label="Filter by account"
              className="t-small bg-transparent border-b border-rule py-1 outline-none
                         focus:border-accent text-ink-muted rounded-sm"
            >
              <option value="">All accounts</option>
              {mockAccounts.map((a) => (
                <option key={a.account_id} value={a.account_id}>{a.name}</option>
              ))}
            </select>

            <select
              value={categoryFilter ?? ""}
              onChange={(e) => setParam("category", e.target.value || null)}
              aria-label="Filter by category"
              className="t-small bg-transparent border-b border-rule py-1 outline-none
                         focus:border-accent text-ink-muted rounded-sm"
            >
              <option value="">All categories</option>
              {categories.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div className={`${LEDGER_GRID} px-1 pb-2 rule-b`}>
          <span className="t-label">Date</span>
          <span className="t-label">Merchant</span>
          <span className="t-label">Category</span>
          <span className="t-label">Account</span>
          <span className="t-label text-right">Amount</span>
        </div>

        {entries.length === 0 ? (
          <EmptyState message="No transactions match these filters." />
        ) : (
          entries.map((e) =>
            e.kind === "transfer" ? (
              <TransferPair
                key={e.group.transfer_group_id}
                group={e.group}
                source={e.source}
                destination={e.destination}
                sourceAccountName={accountName(e.source.account_id)}
                destAccountName={accountName(e.destination.account_id)}
              />
            ) : (
              <TransactionRow
                key={e.transaction.transaction_id}
                txn={e.transaction}
                accountName={accountName(e.transaction.account_id)}
                onSelect={setSelected}
                selected={selected?.transaction_id === e.transaction.transaction_id}
              />
            ),
          )
        )}
      </div>

      {/* Right-side panel, not a modal — keeps list context (DESIGN.md §4). */}
      {selected && <DetailPanel txn={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
