import { useMemo, useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Money } from "@/components/ui/Money";
import { Stat, StatRow } from "@/components/ui/StatRow";
import { EmptyState, ErrorState, Section, SkeletonRows } from "@/components/ui/primitives";
import { Sankey } from "@/components/charts/Sankey";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { formatDateLong, toISODate } from "@/utils/date";
import { moneyToString, parseAmount } from "@/utils/money";
import type { CashFlowReport } from "@/types";

interface Range {
  from: string;
  to: string;
}

/** Ranges are whole months back from today, so "Last 3 months" means three
 *  complete months rather than a 90-day window that cuts a month in half. */
function presets(): { label: string; range: Range }[] {
  const today = new Date();
  const y = today.getFullYear();
  const m = today.getMonth();
  const to = toISODate(today);
  return [
    { label: "This month", range: { from: toISODate(new Date(y, m, 1)), to } },
    { label: "Last 3 months", range: { from: toISODate(new Date(y, m - 2, 1)), to } },
    { label: "Year to date", range: { from: toISODate(new Date(y, 0, 1)), to } },
    { label: "Last 12 months", range: { from: toISODate(new Date(y, m - 11, 1)), to } },
  ];
}

function RangeControl({
  range,
  options,
  onChange,
}: {
  range: Range;
  options: { label: string; range: Range }[];
  onChange: (range: Range) => void;
}) {
  return (
    <div className="rule-b pb-3 mb-8 flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
      <div className="flex flex-wrap items-center gap-4">
        {options.map((o) => {
          const active = o.range.from === range.from && o.range.to === range.to;
          return (
            <button
              key={o.label}
              onClick={() => onChange(o.range)}
              aria-pressed={active}
              /* Active state is a violet hairline, matching the nav marker.
                 No pills, no filled chips (DESIGN.md §3.1, §3.5). */
              className={`t-small pb-1 border-b transition-colors ${
                active
                  ? "text-ink font-medium border-accent"
                  : "text-ink-muted hover:text-ink border-transparent"
              }`}
            >
              {o.label}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        {(["from", "to"] as const).map((field) => (
          <span key={field} className="flex items-center gap-2">
            {field === "to" && <span className="t-small text-ink-faint">to</span>}
            <input
              type="date"
              value={range[field]}
              aria-label={field === "from" ? "Start date" : "End date"}
              /* Each end bounds the other. Without this the picker will happily
                 hand back a start after the end, and the API is asked for a
                 range that cannot contain anything. */
              {...(field === "from" ? { max: range.to } : { min: range.from })}
              onChange={(e) => e.target.value && onChange({ ...range, [field]: e.target.value })}
              /* color-scheme drives the native picker's own chrome; without it
                 the calendar widget stays light-on-light in dark mode. */
              className="t-num-sm bg-transparent text-ink border border-rule rounded-sm px-2 py-1 [color-scheme:light] dark:[color-scheme:dark]"
            />
          </span>
        ))}
      </div>
    </div>
  );
}

/** One of the four summary numbers. Bare, hairline-separated, no card. */

export function Reports() {
  const options = useMemo(presets, []);
  const [range, setRange] = useState<Range>(
    () => options[2]?.range ?? { from: "2026-01-01", to: toISODate(new Date()) },
  );

  const { data, loading, error, refetch } = useApi<CashFlowReport>(
    "cashflow",
    () => api.getCashFlowReport(range.from, range.to),
    [range.from, range.to],
  );

  const header = (
    <>
      <PageHeader
        title="Reports"
        meta={`${formatDateLong(range.from)} — ${formatDateLong(range.to)}`}
      />
      <RangeControl range={range} options={options} onChange={setRange} />
    </>
  );

  if (loading) {
    return (
      <>
        {header}
        <SkeletonRows count={10} />
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        {header}
        <ErrorState
          reason={error?.message ?? "The report came back empty."}
          onRetry={refetch}
        />
      </>
    );
  }

  const income = parseAmount(data.total_income);
  const expenses = parseAmount(data.total_expenses);
  const net = parseAmount(data.net_income);
  // Null is a real answer from the backend, not a missing one: there is no
  // meaningful rate when nothing came in, or when spending dwarfs income by
  // enough that the percentage is noise. `parseAmount` would quietly turn it
  // into 0, which reads as "you kept none of it" — a claim the report is not
  // making.
  const rate = data.savings_rate === null ? null : parseAmount(data.savings_rate);
  const nothingToShow = income === 0 && expenses === 0;

  // Money moved between the user's own accounts is still being reported as an
  // ordinary category, which double-counts it on both sides. Detected from the
  // data rather than hardcoded, so the note disappears by itself once the
  // backend starts pairing transfers — the numbers are its business, not ours.
  const transferCategories = data.sankey.nodes.filter((n) =>
    /^(src|exp):TRANSFER_/.test(n.id),
  );

  const sankeyLabel =
    `Cash flow Sankey diagram, ${formatDateLong(data.date_from)} to ` +
    `${formatDateLong(data.date_to)}. ${moneyToString(data.total_income)} of income flows to ` +
    `${moneyToString(data.total_expenses)} of spending across ` +
    `${data.sankey.nodes.filter((n) => n.column === 2).length} destinations. ` +
    `Ribbon thickness is amount. Full figures follow as a list.`;

  return (
    <>
      {header}

      {/* Four figures on one line, outlined. See components/ui/StatRow. */}
      <StatRow>
        <Stat label="Total income">
          <Money amount={data.total_income} type="INCOME" exact={false} size="lg" />
        </Stat>
        <Stat label="Total expenses">
          {/* Expenses are ink, not red. Spending is the normal state of a
              ledger, not an error (DESIGN.md §3.2). */}
          <Money amount={data.total_expenses} exact={false} size="lg" />
        </Stat>
        <Stat label="Net income">
          {/* forceSign, not the default income convention: <Money> renders a
              leading + only for positive values, so a negative net would
              otherwise print as a bare, positive-looking amount. Suppressed at
              exactly zero, where "+$0" would be nonsense. */}
          <Money
            amount={data.net_income}
            type={net >= 0 ? "INCOME" : undefined}
            forceSign={net !== 0}
            exact={false}
            size="lg"
          />
        </Stat>
        <Stat label="Savings rate">
          {/* A percentage, not money — so not a <Money>. Still tabular, still
              with the unit receding. Negative renders ink, not red: reserved
              for states that are actually broken (DESIGN.md §3.2). */}
          {rate === null ? (
            <span
              className="t-num-lg tabular-nums text-ink-faint"
              aria-label="No meaningful savings rate for this period"
            >
              <span aria-hidden="true">—</span>
            </span>
          ) : (
            <span
              className={`t-num-lg tabular-nums ${rate > 0 ? "text-income" : "text-ink"}`}
              aria-label={`${rate.toFixed(1)} percent of income kept`}
            >
              <span aria-hidden="true">
                {rate < 0 ? "−" : rate > 0 ? "+" : ""}
                {Math.abs(rate).toFixed(1)}
                <span className="num-unit">%</span>
              </span>
            </span>
          )}
        </Stat>
      </StatRow>

      <Section title="Where the money went">
        {nothingToShow ? (
          <EmptyState message="No income or spending in this period. Try a wider date range." />
        ) : (
          <>
            <Sankey data={data.sankey} label={sankeyLabel} />

            {/* Semantic legend only — three meanings, three colors. There is no
                per-category color to legend, which is the point. */}
            <div className="mt-6 flex flex-wrap gap-4 t-small text-ink-faint">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-income inline-block" aria-hidden="true" /> Income
              </span>
              {net > 0 && (
                <span className="flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-transfer inline-block" aria-hidden="true" /> Net income
                </span>
              )}
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-ink/75 inline-block" aria-hidden="true" /> Expenses
              </span>
              <span>Thickness is amount. Hover a ribbon for its value.</span>
            </div>

            {net < 0 && (
              <p className="mt-4 t-small text-ink-muted max-w-[68ch]">
                Outflows exceeded inflows by{" "}
                {/* The sentence already says which way this went, so the amount
                    is a magnitude: "exceeded by −$63,863" is a double negative.
                    EXPENSE is the type that renders an outflow bare. */}
                <Money amount={data.net_income} type="EXPENSE" exact={false} size="sm" /> in this
                period. The
                faded lower part of the Income column is that difference — spending this report
                has no matching income for.
              </p>
            )}

            {transferCategories.length > 0 && (
              <p className="mt-2 t-small text-ink-muted max-w-[68ch]">
                <span className="text-transfer">Transfers are not yet detected.</span> Money moved
                between your own accounts still appears here as an ordinary category, so it is
                counted on both sides and inflates every total above.
              </p>
            )}
          </>
        )}
      </Section>
    </>
  );
}
