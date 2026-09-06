import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Money } from "@/components/ui/Money";
import { ComputedAt, Section } from "@/components/ui/primitives";
import { Sparkline } from "@/components/charts/Sparkline";
import { CategoryBars } from "@/components/charts/CategoryBars";
import { CashFlowBars } from "@/components/charts/CashFlowBars";
import { TransactionRow } from "@/components/ledger/TransactionRow";
import { TransferPair } from "@/components/ledger/TransferPair";
import { accountName, buildLedger, mockDashboard, mockTransactions, mockTransferGroups } from "@/api/mock";
import { relativeTime } from "@/utils/date";
import { parseAmount } from "@/utils/money";

/**
 * Single column, top to bottom, decreasing importance (DESIGN.md §4).
 * Every number here is clickable and lands on the transactions that sum to it.
 */
export function Overview() {
  const navigate = useNavigate();
  const d = mockDashboard;

  const entries = buildLedger(mockTransactions, mockTransferGroups);
  const recent = entries.slice(0, 6);
  const suggested = mockTransferGroups.filter((g) => g.status === "SUGGESTED");
  const uncategorized = mockTransactions.filter(
    (t) => !t.category && t.transaction_type !== "TRANSFER",
  );

  return (
    <>
      <PageHeader title="Overview" meta="September 2026" />

      {/* ── Net worth — the one number that matters most ──────────────────── */}
      <section className="pb-8">
        <div className="flex items-start justify-between gap-8">
          <div>
            <div className="t-label mb-2">Net worth</div>
            <Money amount={d.net_worth} size="lg" exact={false} />
            <div className="mt-1.5 flex items-baseline gap-2">
              <Money amount={d.net_worth_change_month} type="INCOME" size="sm" exact={false} />
              <span className="t-small text-ink-faint">this month</span>
            </div>
          </div>
          <div className="w-[280px] text-ink-muted shrink-0 pt-2">
            <Sparkline data={d.net_worth_series} height={48} />
          </div>
        </div>
      </section>

      {/* ── This month: three bare numbers, hairline separated. No cards. ──── */}
      <Section>
        <div className="grid grid-cols-3 gap-px bg-rule">
          {[
            { label: "Income", amount: d.month_income, type: "INCOME" as const, to: "/ledger?type=INCOME" },
            { label: "Spending", amount: d.month_spending, type: undefined, to: "/ledger?type=EXPENSE" },
            { label: "Net", amount: d.month_net, type: "INCOME" as const, to: "/ledger" },
          ].map((s) => (
            <button
              key={s.label}
              onClick={() => navigate(s.to)}
              className="bg-canvas text-left py-4 pr-4 row-hover"
            >
              <div className="t-label mb-1.5">{s.label}</div>
              <Money amount={s.amount} type={s.type} exact={false} size="lg" />
            </button>
          ))}
        </div>
        <p className="mt-3 t-small text-ink-faint">
          {/* State the exclusion explicitly — it is the product's core claim. */}
          Excludes <span className="text-transfer">$4,000.00</span> in transfers between your own
          accounts.
        </p>
      </Section>

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

      <Section title="Spending by category">
        <CategoryBars
          data={d.spending_by_category}
          onSelect={(c) => navigate(`/ledger?category=${encodeURIComponent(c)}`)}
        />
      </Section>

      <Section
        title="Recent activity"
        action={
          <button onClick={() => navigate("/ledger")} className="t-small text-accent hover:underline">
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
                <button onClick={() => navigate("/ledger")} className="t-small text-accent hover:underline">
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
                <button onClick={() => navigate("/ledger")} className="t-small text-accent hover:underline">
                  Categorize
                </button>
              </li>
            )}
          </ul>
        </Section>
      )}

      <footer className="pt-6 rule-t">
        <ComputedAt when={relativeTime(d.computed_at)} />
        {" · "}
        <span className="t-small text-ink-faint">
          {mockTransactions.filter((t) => parseAmount(t.amount) !== 0).length} transactions this month
        </span>
      </footer>
    </>
  );
}
