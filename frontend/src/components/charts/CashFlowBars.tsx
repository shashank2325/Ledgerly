import { parseAmount, moneyToString } from "@/utils/money";
import { formatMonth } from "@/utils/date";
import type { MonthlyCashFlow } from "@/types";

/**
 * Income vs. expense bar pair — DESIGN.md §3.6 chart type 4.
 * Two bars per month: income green, expense ink. No gridlines, no y-axis.
 */
export function CashFlowBars({ data }: { data: MonthlyCashFlow[] }) {
  const max = Math.max(
    ...data.flatMap((d) => [parseAmount(d.income), Math.abs(parseAmount(d.expenses))]),
    1,
  );

  return (
    <div
      className="flex items-stretch gap-1.5 md:gap-2 h-28 md:h-36"
      role="img"
      aria-label="Monthly income versus expenses"
    >
      {data.map((d) => (
        <div key={d.month} className="flex-1 flex flex-col group">
          {/* min-h-0 is required: without it the flex item refuses to shrink
              below its content height and the bars collapse to zero. */}
          <div className="flex-1 min-h-0 flex items-end justify-center gap-[3px]">
            <div
              className="w-1/2 max-w-6 bg-income/80 group-hover:bg-income transition-colors"
              style={{ height: `${(parseAmount(d.income) / max) * 100}%` }}
              title={`${d.month} income ${moneyToString(d.income)}`}
            />
            <div
              className="w-1/2 max-w-6 bg-ink/70 group-hover:bg-ink transition-colors"
              style={{ height: `${(Math.abs(parseAmount(d.expenses)) / max) * 100}%` }}
              title={`${d.month} expenses ${moneyToString(d.expenses)}`}
            />
          </div>
          <span className="t-num-sm text-ink-faint text-center pt-2 shrink-0">
            {formatMonth(d.month)}
          </span>
        </div>
      ))}
    </div>
  );
}
