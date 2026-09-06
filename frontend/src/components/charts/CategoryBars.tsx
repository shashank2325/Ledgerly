import { Money } from "@/components/ui/Money";
import { parseAmount } from "@/utils/money";
import type { CategorySpend } from "@/types";

/**
 * Horizontal ranked bars — DESIGN.md §3.6 chart type 1.
 * Label left, bar, amount right. No axis, no gridlines, no legend.
 *
 * Explicitly NOT a pie chart. Pies are the visual signature of every budgeting
 * app and they are bad at the one job: comparing magnitudes.
 *
 * Categories are distinguished by LABEL, never by color — that is what kills
 * the rainbow look and keeps the interface calm (DESIGN.md §3.2).
 */
export function CategoryBars({
  data,
  onSelect,
}: {
  data: CategorySpend[];
  onSelect?: (category: string) => void;
}) {
  const max = Math.max(...data.map((d) => Math.abs(parseAmount(d.amount))), 1);

  return (
    <div>
      {data.map((d) => {
        const pct = (Math.abs(parseAmount(d.amount)) / max) * 100;
        return (
          <button
            key={d.category}
            onClick={() => onSelect?.(d.category)}
            className="w-full text-left group py-2 rule-b last:border-b-0 row-hover"
            /* Every chart element navigates to the filtered transactions that
               sum to it — the "traceable to source" principle (DESIGN.md §1). */
            title={`${d.transaction_count} transactions`}
          >
            <div className="flex items-baseline justify-between mb-1.5">
              <span className="t-body">{d.category}</span>
              <span className="flex items-baseline gap-2">
                <span className="t-num-sm text-ink-faint">{d.transaction_count}</span>
                <Money amount={d.amount} exact={false} />
              </span>
            </div>
            <div className="h-[3px] bg-rule">
              <div
                className="h-full bg-ink transition-[width] duration-300 group-hover:bg-accent"
                style={{ width: `${pct}%` }}
              />
            </div>
          </button>
        );
      })}
    </div>
  );
}
