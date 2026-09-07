import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Money } from "@/components/ui/Money";
import { Stat, StatRow } from "@/components/ui/StatRow";
import { Section } from "@/components/ui/primitives";
import { CategoryBars } from "@/components/charts/CategoryBars";
import { CashFlowBars } from "@/components/charts/CashFlowBars";
import { TransactionRow } from "@/components/ledger/TransactionRow";
import { TransferPair } from "@/components/ledger/TransferPair";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { buildLedger } from "@/utils/ledger";
import { ErrorState, SkeletonRows } from "@/components/ui/primitives";
import { parseAmount } from "@/utils/money";
import type { Account } from "@/types";

/**
 * Single column, top to bottom, decreasing importance (DESIGN.md §4).
 * Every number here is clickable and lands on the transactions that sum to it.
 */
export function Overview() {
  const navigate = useNavigate();
  const { data: d, loading, error, refetch } = useApi(() => api.getDashboard(), []);
  const { data: recentData } = useApi(() => api.getTransactions({ limit: 12 }), []);
  const { data: accountsData } = useApi(() => api.getAccounts(), []);

  const accountName = (id: string) => {
    const account = (accountsData?.accounts ?? []).find((a: Account) => a.account_id === id);
    return account ? `${account.name} ··${account.mask ?? ""}` : id;
  };

  if (loading) {
    return (
      <>
        <PageHeader title="Overview" />
        <SkeletonRows count={10} />
      </>
    );
  }
  if (error || !d) {
    return (
      <>
        <PageHeader title="Overview" />
        <ErrorState reason={error?.message ?? "No data"} onRetry={refetch} />
      </>
    );
  }

  const entries = buildLedger(recentData?.transactions ?? [], recentData?.transfer_groups ?? []);
  const recent = entries.slice(0, 6);
  const suggested = (recentData?.transfer_groups ?? []).filter((g) => g.status === "SUGGESTED");
  const uncategorized = (recentData?.transactions ?? []).filter(
    (t) => !t.category && t.transaction_type !== "TRANSFER",
  );

  return (
    <>
      <PageHeader title="Overview" meta={d.month} />

      {/* ── This month: three figures on one line, outlined. ──────────────── */}
      <Section>
        <StatRow>
          {/* Net worth sits with the others rather than above them: it is the
              same kind of figure and separating it implied a hierarchy the
              numbers do not have. It carries the trend because it is the only
              one of the four with a meaningful history. */}
          <Stat label="Net worth" trend={d.net_worth_series}>
            <Money amount={d.net_worth} exact={false} size="lg" />
            <div className="mt-1 t-small text-ink-faint">
              {d.account_count} {d.account_count === 1 ? "account" : "accounts"}
            </div>
          </Stat>
          {[
            { label: "Income", amount: d.month_income, type: "INCOME" as const, to: "/app/ledger?type=INCOME" },
            { label: "Spending", amount: d.month_spending, type: undefined, to: "/app/ledger?type=EXPENSE" },
            // Net carries no type: it can be negative, and <Money> only emits a
            // leading + for positives — typing it INCOME would print a negative
            // net as a bare, positive-looking figure.
            { label: "Net", amount: d.month_net, type: undefined, to: "/app/ledger" },
          ].map((stat) => (
            <Stat key={stat.label} label={stat.label} onClick={() => navigate(stat.to)}>
              <Money amount={stat.amount} type={stat.type} exact={false} size="lg" />
            </Stat>
          ))}
        </StatRow>
        {parseAmount(d.month_transfers) > 0 && (
          <p className="mt-3 t-small text-ink-faint">
            {/* State the exclusion explicitly — it is the product's core claim. */}
            Excludes <span className="text-transfer">${parseAmount(d.month_transfers).toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>{" "}
            in transfers between your own accounts.
          </p>
        )}
      </Section>

      {d.cash_flow.length > 0 && (
      <Section title="Cash flow">
        <CashFlowBars data={d.cash_flow} />
        <div className="mt-3 flex gap-4 t-small text-ink-faint">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-income inline-block" aria-hidden="true" /> Income
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 bg-ink/75 inline-block" aria-hidden="true" /> Expenses
          </span>
        </div>
      </Section>
      )}

      {d.spending_by_category.length > 0 && (
      <Section title="Spending by category">
        <CategoryBars
          data={d.spending_by_category}
          onSelect={(c) => navigate(`/app/ledger?category=${encodeURIComponent(c)}`)}
        />
      </Section>
      )}

      <Section
        title="Recent activity"
        action={
          <button onClick={() => navigate("/app/ledger")} className="t-small text-accent hover:underline">
            View ledger
          </button>
        }
      >
        {recent.map((e) =>
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
            />
          ),
        )}
      </Section>

      {/* ── Only renders when non-empty ───────────────────────────────────── */}
      {(suggested.length > 0 || uncategorized.length > 0) && (
        <Section title="Needs attention">
          <ul className="flex flex-col">
            {suggested.length > 0 && (
              <li className="row justify-between">
                <span className="t-body">
                  {suggested.length} possible transfer{suggested.length > 1 ? "s" : ""} to confirm
                </span>
                <button onClick={() => navigate("/app/ledger")} className="t-small text-accent hover:underline">
                  Review
                </button>
              </li>
            )}
            {uncategorized.length > 0 && (
              <li className="row justify-between">
                <span className="t-body">
                  {uncategorized.length} uncategorized transaction
                  {uncategorized.length > 1 ? "s" : ""}
                </span>
                <button onClick={() => navigate("/app/ledger")} className="t-small text-accent hover:underline">
                  Categorize
                </button>
              </li>
            )}
          </ul>
        </Section>
      )}

      <footer className="pt-6 rule-t">
        <span className="t-small text-ink-faint">
          Live from Athena · {d.account_count} accounts
        </span>
      </footer>
    </>
  );
}
