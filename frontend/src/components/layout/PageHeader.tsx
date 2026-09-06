import type { ReactNode } from "react";

export function PageHeader({
  title,
  meta,
  action,
}: {
  title: string;
  meta?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className="flex items-baseline justify-between mb-8">
      <div className="flex items-baseline gap-3">
        <h1 className="t-h1">{title}</h1>
        {meta && <span className="t-small text-ink-faint">{meta}</span>}
      </div>
      {action}
    </header>
  );
}
