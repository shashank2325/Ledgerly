import type { ReactNode } from "react";
import { Sparkline } from "@/components/charts/Sparkline";

/**
 * A row of headline figures.
 *
 * Outlined rather than bare. DESIGN.md §3.1 rules out cards — shadowed,
 * elevated boxes floating on a tinted ground — and this is not that: a single
 * 1px hairline in the existing rule color, square corners, no shadow, no fill.
 * It contains the group without introducing an elevation system.
 *
 * ONE ROW on desktop, STACKED on mobile.
 *
 * On a wide screen the figures are peers read left to right, and wrapping them
 * onto two lines breaks that — the eye reads a grid instead of a sequence.
 * On a phone there is no such thing as one row: four cells either scroll (so
 * you cannot see them at once, and two are permanently offscreen) or shrink
 * until the numbers wrap. Stacking shows all four at full size in one glance,
 * which is what the row was for in the first place. The divider flips axis with
 * the layout so the hairline always separates rather than crosses.
 */
export function StatRow({ children }: { children: ReactNode }) {
  return (
    <div className="md:overflow-x-auto md:-mx-1 md:px-1">
      <div
        className="border border-rule flex flex-col divide-y divide-rule
                   md:flex-row md:divide-y-0 md:divide-x md:min-w-max"
      >
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
          className="absolute inset-x-0 bottom-0 h-[58px] text-ink-muted
                     opacity-40 dark:opacity-50 pointer-events-none"
          aria-hidden="true"
        >
          <Sparkline data={trend} height={58} />
        </div>
      )}
      {/* relative + a canvas-tinted backdrop keeps the line strictly behind the
          number. A trend running through the digits costs legibility of the
          figure, which is the thing that actually matters. */}
      <div className="relative">
        <div className="t-label mb-1.5">{label}</div>
        {children}
        {hint && <div className="mt-1">{hint}</div>}
      </div>
    </>
  );

  // min-w applies only from md, where cells sit side by side and the row
  // scrolls rather than crushing a number onto two lines. Stacked on mobile,
  // each cell already has the full width.
  //
  // flex-col + justify-start forces identical top alignment across cells:
  // without it <button> centres its content vertically while <div> does not,
  // so the tallest cell (the one with a hint) pushes every other label down.
  const shell =
    "relative overflow-hidden flex-1 md:min-w-[176px] " +
    "px-4 md:px-5 py-3.5 md:py-4 text-left " +
    "flex flex-col justify-start";

  return onClick ? (
    <button onClick={onClick} className={`${shell} row-hover transition-colors`}>
      {body}
    </button>
  ) : (
    <div className={shell}>{body}</div>
  );
}
