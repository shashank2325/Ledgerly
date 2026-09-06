import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/primitives";
import { mockAccounts } from "@/api/mock";
import { relativeTime } from "@/utils/date";

const TABS = ["Connections", "Categories", "Rules", "Data"] as const;
type Tab = (typeof TABS)[number];

export function Settings() {
  const [tab, setTab] = useState<Tab>("Connections");

  const items = [...new Map(mockAccounts.map((a) => [a.item_id, a])).values()];
  const categories = [
    ["Housing", ["Rent", "Utilities"]],
    ["Food", ["Groceries", "Restaurants", "Coffee"]],
    ["Transportation", ["Gas", "Rideshare", "Transit"]],
    ["Shopping", ["General", "Clothing", "Electronics"]],
    ["Subscriptions", ["Streaming", "Software"]],
    ["Income", ["Salary", "Interest"]],
  ] as const;

  return (
    <>
      <PageHeader title="Settings" />

      <div className="flex gap-5 rule-b-strong pb-3 mb-1" role="tablist">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
            className={`t-small transition-colors ${
              tab === t ? "text-ink font-medium" : "text-ink-muted hover:text-ink"
            }`}>
            {t}
          </button>
        ))}
      </div>

      <div className="py-6">
        {tab === "Connections" && (
          <>
            {items.map((a) => (
              <div key={a.item_id} className="row justify-between px-1">
                <span className="flex items-baseline gap-3">
                  <span className="t-body">{a.institution_name}</span>
                  <span className="t-small text-ink-faint">
                    {mockAccounts.filter((x) => x.item_id === a.item_id).length} accounts
                  </span>
                </span>
                <span className="flex items-center gap-4">
                  <span className="t-small text-ink-faint">
                    {a.last_synced_at ? relativeTime(a.last_synced_at) : "never"}
                  </span>
                  <button className="t-small text-ink-muted hover:text-negative">Remove</button>
                </span>
              </div>
            ))}
            <button className="mt-4 t-small text-accent hover:underline">Connect an institution</button>
          </>
        )}

        {tab === "Categories" && (
          <div className="flex flex-col">
            {categories.map(([parent, subs]) => (
              <div key={parent} className="py-2 rule-b">
                <div className="t-body">{parent}</div>
                <div className="t-small text-ink-faint mt-0.5">{subs.join(" · ")}</div>
              </div>
            ))}
            <p className="mt-4 t-small text-ink-faint">
              Seeded from Plaid's taxonomy, then overridable. Editing arrives with the rules engine.
            </p>
          </div>
        )}

        {tab === "Rules" && (
          <EmptyState
            message="No rules yet. Rules automatically categorize transactions and can be applied to your full history."
            action={<button className="t-small text-accent hover:underline">Create a rule</button>}
          />
        )}

        {tab === "Data" && (
          <div className="flex flex-col">
            {[
              ["Last sync", "32 minutes ago"],
              ["Transactions stored", "16"],
              ["Raw payloads retained", "All — since first sync"],
            ].map(([k, v]) => (
              <div key={k} className="row justify-between px-1">
                <span className="t-body">{k}</span>
                <span className="t-small text-ink-muted">{v}</span>
              </div>
            ))}
            <div className="mt-5 flex flex-col gap-2 items-start">
              <button className="t-small text-accent hover:underline">Sync now</button>
              <button className="t-small text-accent hover:underline">Export CSV</button>
              <button className="t-small text-accent hover:underline">
                Reprocess history from raw
              </button>
            </div>
            <p className="mt-4 t-small text-ink-faint max-w-md">
              Raw source data is never destroyed. Categorization and transfer detection can be
              re-run over your full history at any time without data loss.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
