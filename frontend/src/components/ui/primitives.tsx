import type { ReactNode } from "react";

/** Section label — uppercase, tracked, muted, so the eye skips it and lands
 *  on the data. */
export function Label({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`t-label ${className}`}>{children}</div>;
}

/** A page section. Hairline separated — no cards, no boxes (DESIGN.md §3.1). */
export function Section({
  title,
  action,
  children,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="py-8 rule-t first:rule-t-0 first:pt-0">
      {(title || action) && (
        <header className="flex items-baseline justify-between mb-4">
          {title && <h2 className="t-label">{title}</h2>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

/** Empty state: one sentence and the single action that fixes it.
 *  No illustrations (DESIGN.md §3.8). */
export function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="py-12 text-ink-muted t-body">
      <p>{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

/** Error state: the actual reason and a retry. Never "Something went wrong." */
export function ErrorState({ reason, onRetry }: { reason: string; onRetry?: () => void }) {
  return (
    <div className="py-12" role="alert">
      <p className="t-body text-negative">{reason}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 t-body text-accent underline underline-offset-2 hover:no-underline"
        >
          Retry
        </button>
      )}
    </div>
  );
}

/** Loading: hairline skeleton rows at the exact height of real rows.
 *  No spinners, no shimmer. */
export function SkeletonRows({ count = 6 }: { count?: number }) {
  return (
    <div aria-busy="true" aria-live="polite" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="row">
          <div className="skeleton h-3 w-full" style={{ maxWidth: `${55 + ((i * 13) % 35)}%` }} />
        </div>
      ))}
    </div>
  );
}

/** Stale-data marker. If analytics are older than the last sync, say so
 *  inline — never show stale numbers silently. */
export function ComputedAt({ when }: { when: string }) {
  return <span className="t-small text-ink-faint">Computed {when}</span>;
}
