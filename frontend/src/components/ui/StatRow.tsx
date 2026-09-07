import type { ReactNode } from "react";
import { Sparkline } from "@/components/charts/Sparkline";

/**
 * A row of headline figures.
 *
 * Outlined rather than bare. DESIGN.md §3.1 rules out cards — shadowed,
 * elevated boxes floating on a tinted ground — and this is not that: a single
 * 1px hairline in the existing rule color, square corners, no shadow, no fill.
 * It contains the row without introducing an elevation system.
 *
 * Always ONE row. Wrapping four stats onto two lines breaks the scan — the eye
 * reads a grid instead of a sequence, and the fourth figure stops looking
 * peer-level with the first. Below the width where they fit, the row scrolls
 * inside its own container, which §3.5 already requires of wide content.
 */
export function StatRow({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <div className="border border-rule divide-x divide-rule flex min-w-max">
        {children}
      </div>
    </div>
  );
}

export function Stat({
  label,
  children,
  onClick,
  hint,
  trend,
}: {
  label: string;
  children: ReactNode;
  onClick?: () => void;
  hint?: ReactNode;
  /** Optional trend drawn behind the figure. */
  trend?: { date: string; value: string }[];
}) {
  const body = (
    <>
      {/* Behind the number, deliberately faint. It is context for the figure,
          not a chart in its own right — at this size it can show direction and
          rough shape and nothing more, so competing with the value it sits
          behind would be a lie about its precision. */}
      {trend && trend.length > 1 && (
        <div
          className="absolute inset-0 flex items-end text-ink opacity-[0.16]
                     dark:opacity-[0.22] pointer-events-none"
          aria-hidden="true"
        >
          <Sparkline data={trend} height={64} />
        </div>
      )}
      <div className="relative">
        <div className="t-label mb-1.5">{label}</div>
        {children}
        {hint && <div className="mt-1">{hint}</div>}
      </div>
    </>
  );

  // min-w keeps every cell wide enough for a seven-figure amount plus its
  // label, so the row scrolls rather than crushing a number into two lines.
  // flex-col + justify-start forces identical top alignment across cells.
  // Without it, <button> centres its content vertically while <div> does not,
  // so the tallest cell (the one with a hint) pushes every other label down.
  const shell =
    "relative overflow-hidden flex-1 min-w-[176px] px-5 py-4 text-left " +
    "flex flex-col justify-start";

  return onClick ? (
    <button onClick={onClick} className={`${shell} row-hover transition-colors`}>
      {body}
    </button>
  ) : (
    <div className={shell}>{body}</div>
  );
}
