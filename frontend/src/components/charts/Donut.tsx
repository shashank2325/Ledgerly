import { useState } from "react";
import { Money } from "@/components/ui/Money";
import { parseAmount } from "@/utils/money";
import type { CategorySpend } from "@/types";

/**
 * Spending by category, part-to-whole.
 *
 * A donut is only defensible for part-to-whole AT A GLANCE, capped at six
 * segments — beyond that, arc lengths of similar size become genuinely
 * indistinguishable and a ranked bar is strictly better. So: top five plus
 * "Other". The precise comparison lives in the legend's numbers and in the
 * ranked bars further down the page; this answers "roughly how is it split".
 *
 * Colors come from the validated series palette (see index.css). They are
 * assigned in fixed order by rank and never cycled. Three light-mode slots sit
 * below 3:1 contrast, which the validator flags as requiring relief — hence the
 * legend always carries a visible label AND its value. Identity is never
 * color-alone.
 */

const MAX_SEGMENTS = 6;
const SERIES = [
  "var(--c-series-1)", "var(--c-series-2)", "var(--c-series-3)",
  "var(--c-series-4)", "var(--c-series-5)", "var(--c-series-6)",
] as const;

// Geometry in a 100-unit box. A thin ring, consistent with thin marks.
const R = 38;
const STROKE = 13;
const CIRCUMFERENCE = 2 * Math.PI * R;
// 2px of surface between segments so adjacent fills never touch.
const GAP = 2;

function humanize(category: string): string {
  return category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function Donut({
  data,
  onSelect,
}: {
  data: CategorySpend[];
  onSelect?: (category: string) => void;
}) {
  const [active, setActive] = useState<number | null>(null);

  const ranked = [...data].sort(
    (a, b) => Math.abs(parseAmount(b.amount)) - Math.abs(parseAmount(a.amount)),
  );

  // Fold the tail into "Other" rather than generating a seventh hue.
  const head = ranked.slice(0, MAX_SEGMENTS - 1);
  const tail = ranked.slice(MAX_SEGMENTS - 1);
  const segments = [...head];
  if (tail.length) {
    segments.push({
      category: "OTHER",
      // Negated to match the sign convention of the rows it summarises — the
      // API returns spending as negative, and a positive "Other" beside
      // negative siblings reads as money coming in.
      amount: String(-tail.reduce((sum, d) => sum + Math.abs(parseAmount(d.amount)), 0)),
      transaction_count: tail.reduce((sum, d) => sum + d.transaction_count, 0),
    });
  }

  const total = segments.reduce((sum, d) => sum + Math.abs(parseAmount(d.amount)), 0);
  if (total <= 0) return null;

  let offset = 0;
  const arcs = segments.map((segment, index) => {
    const value = Math.abs(parseAmount(segment.amount));
    const share = value / total;
    const length = Math.max(share * CIRCUMFERENCE - GAP, 0.5);
    const arc = {
      segment,
      index,
      value,
      share,
      length,
      offset,
      color: SERIES[index % SERIES.length]!,
    };
    offset += share * CIRCUMFERENCE;
    return arc;
  });

  const focused = active !== null ? arcs[active] : null;

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-6 sm:gap-8">
      <div className="relative shrink-0 self-center sm:self-auto" style={{ width: 168, height: 168 }}>
        <svg
          viewBox="0 0 100 100"
          className="w-full h-full -rotate-90"
          role="img"
          aria-label={`Spending split across ${segments.length} categories, ${
            segments.map((s) => humanize(s.category)).join(", ")
          }`}
        >
          {arcs.map((arc) => (
            <circle
              key={arc.segment.category}
              cx="50"
              cy="50"
              r={R}
              fill="none"
              stroke={arc.color}
              strokeWidth={active === arc.index ? STROKE + 3 : STROKE}
              strokeDasharray={`${arc.length} ${CIRCUMFERENCE - arc.length}`}
              strokeDashoffset={-arc.offset}
              className="transition-[stroke-width,opacity] duration-150 cursor-pointer"
              opacity={active === null || active === arc.index ? 1 : 0.35}
              onMouseEnter={() => setActive(arc.index)}
              onMouseLeave={() => setActive(null)}
              onClick={() =>
                arc.segment.category !== "OTHER" && onSelect?.(arc.segment.category)
              }
            />
          ))}
        </svg>

        {/* The hole earns its place by holding the total — the denominator the
            arcs are shares of. Empty, it would be decoration. */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          {focused ? (
            <>
              <span className="t-num text-ink">
                {Math.round(focused.share * 100)}
                <span className="num-unit">%</span>
              </span>
              <span className="t-small text-ink-muted text-center px-6 leading-tight">
                {humanize(focused.segment.category)}
              </span>
            </>
          ) : (
            <>
              <Money amount={String(-total)} exact={false} size="base" />
              <span className="t-label mt-0.5">Total</span>
            </>
          )}
        </div>
      </div>

      {/* Legend. Always present, always carrying the value — identity is never
          conveyed by color alone, and it is the contrast relief the validator
          requires for three of the light-mode slots. */}
      <ul className="flex-1 w-full sm:min-w-[200px] flex flex-col">
        {arcs.map((arc) => (
          <li key={arc.segment.category}>
            <button
              onMouseEnter={() => setActive(arc.index)}
              onMouseLeave={() => setActive(null)}
              onClick={() =>
                arc.segment.category !== "OTHER" && onSelect?.(arc.segment.category)
              }
              className="w-full flex items-baseline gap-2.5 py-1.5 rule-b last:border-b-0
                         text-left row-hover px-1"
            >
              <span
                className="w-2 h-2 shrink-0 translate-y-[-1px]"
                style={{ background: arc.color }}
                aria-hidden="true"
              />
              <span className="t-small truncate flex-1">
                {humanize(arc.segment.category)}
              </span>
              <span className="t-num-sm text-ink-faint shrink-0">
                {Math.round(arc.share * 100)}%
              </span>
              <span className="shrink-0 w-24 text-right">
                <Money amount={arc.segment.amount} exact={false} size="sm" />
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
