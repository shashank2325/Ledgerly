import type { ReactNode } from "react";

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
}: {
  label: string;
  children: ReactNode;
  onClick?: () => void;
  hint?: ReactNode;
}) {
  const body = (
    <>
      <div className="t-label mb-1.5">{label}</div>
      {children}
      {hint && <div className="mt-1">{hint}</div>}
    </>
  );

  // min-w keeps every cell wide enough for a seven-figure amount plus its
  // label, so the row scrolls rather than crushing a number into two lines.
  const shell = "flex-1 min-w-[176px] px-5 py-4 text-left";

  return onClick ? (
    <button onClick={onClick} className={`${shell} row-hover transition-colors`}>
      {body}
    </button>
  ) : (
    <div className={shell}>{body}</div>
  );
}
