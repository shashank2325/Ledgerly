import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/primitives";
import { TransactionRow, LEDGER_GRID } from "@/components/ledger/TransactionRow";
import { TransferPair } from "@/components/ledger/TransferPair";
import { DetailPanel } from "@/components/ledger/DetailPanel";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { buildLedger } from "@/utils/ledger";
import type { Account, Transaction, TransactionType } from "@/types";

const TYPE_FILTERS: { value: TransactionType | "ALL"; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "EXPENSE", label: "Expenses" },
  { value: "INCOME", label: "Income" },
  { value: "TRANSFER", label: "Transfers" },
];

export function Ledger() {
  const [params, setParams] = useSearchParams();
  const [selected, setSelected] = useState<Transaction | null>(null);
  const [searchInput, setSearchInput] = useState(params.get("search") ?? "");

  const typeFilter = (params.get("type") ?? "ALL") as TransactionType | "ALL";
  const categoryFilter = params.get("category");
  const accountFilter = params.get("account");
  const search = params.get("search");

  // Filtering happens in Athena, not in the browser: the client only ever holds
  // one page, so filtering client-side would silently search a subset.
  const { data, loading, error, refetch } = useApi(
    "transactions",
    () =>
      api.getTransactions({
        type: typeFilter === "ALL" ? undefined : typeFilter,
        category: categoryFilter ?? undefined,
        account: accountFilter ?? undefined,
        search: search ?? undefined,
        limit: 200,
      }),
    [typeFilter, categoryFilter, accountFilter, search],
  );

  const { data: accountsData } = useApi("accounts", () => api.getAccounts());
  const accountName = useMemo(() => {
    const byId = new Map((accountsData?.accounts ?? []).map((a: Account) => [a.account_id, a]));
    return (id: string) => {
      const account = byId.get(id);
      return account ? `${account.name} ··${account.mask ?? ""}` : id;
    };
  }, [accountsData]);

  const entries = useMemo(
    () => buildLedger(data?.transactions ?? [], data?.transfer_groups ?? []),
    [data],
  );

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === "ALL" || value === "") next.delete(key);
    else next.set(key, value);
    setParams(next);
  };

  const categories = useMemo(
    () => [...new Set((data?.transactions ?? []).map((t) => t.category).filter(Boolean))] as string[],
    [data],
  );
  const activeFilters =
    [categoryFilter, accountFilter, search].filter(Boolean).length + (typeFilter !== "ALL" ? 1 : 0);

  return (
    <div className="flex gap-0">
      <div className="flex-1 min-w-0">
        <PageHeader
          title="Ledger"
          meta={loading ? "loading…" : `${entries.length} ${entries.length === 1 ? "entry" : "entries"}`}
          action={
            activeFilters > 0 ? (
              <button
                onClick={() => {
                  setParams(new URLSearchParams());
                  setSearchInput("");
                }}
                className="t-small text-accent hover:underline"
              >
                Clear {activeFilters} filter{activeFilters > 1 ? "s" : ""}
              </button>
            ) : undefined
          }
        />

        <div className="sticky top-0 bg-canvas z-10 pb-3 rule-b-strong mb-1">
          <div className="flex items-center gap-4 flex-wrap">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setParam("search", searchInput.trim() || null);
              }}
            >
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search — press Enter"
                aria-label="Search transactions"
                className="t-body bg-transparent border-b border-rule focus:border-accent
                           outline-none py-1 w-56 placeholder:text-ink-faint"
              />
            </form>

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
                         focus:border-accent text-ink-muted rounded-sm max-w-[200px]"
            >
              <option value="">All accounts</option>
              {(accountsData?.accounts ?? []).map((a: Account) => (
                <option key={a.account_id} value={a.account_id}>
                  {a.institution_name} — {a.name}
                </option>
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
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Column headers only exist on desktop: on mobile each row is two
            stacked lines, so a header row would not line up with anything. */}
        <div className={`hidden md:grid ${LEDGER_GRID} px-1 pb-2 rule-b`}>
          <span className="t-label">Date</span>
          <span className="t-label">Merchant</span>
          <span className="t-label">Category</span>
          <span className="t-label">Account</span>
          <span className="t-label text-right">Amount</span>
        </div>

        {loading ? (
          <SkeletonRows count={10} />
        ) : error ? (
          <ErrorState reason={error.message} onRetry={refetch} />
        ) : entries.length === 0 ? (
          <EmptyState
            message={
              activeFilters > 0
                ? "No transactions match these filters."
                : "No transactions yet. Connect an account and run a sync."
            }
          />
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

      {selected && (
        <DetailPanel
          txn={selected}
          accountName={accountName(selected.account_id)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
