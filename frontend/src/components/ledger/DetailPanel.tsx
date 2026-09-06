import { Money } from "@/components/ui/Money";
import { formatDateLong } from "@/utils/date";
import { accountName } from "@/api/mock";
import type { Transaction } from "@/types";

/** Right-side detail panel. Shows the full normalized record and — behind a
 *  disclosure — the raw source, expressing the "traceable to source"
 *  principle at the row level (DESIGN.md §1). */
export function DetailPanel({ txn, onClose }: { txn: Transaction; onClose: () => void }) {
  const rows: [string, React.ReactNode][] = [
    ["Date", formatDateLong(txn.transaction_date)],
    ["Account", accountName(txn.account_id)],
    ["Category", txn.category ? `${txn.category}${txn.subcategory ? ` · ${txn.subcategory}` : ""}` : "Uncategorized"],
    ["Type", <span className={txn.transaction_type === "TRANSFER" ? "text-transfer" : ""}>{txn.transaction_type}</span>],
    ["Status", txn.is_pending ? <span className="text-pending">Pending</span> : "Posted"],
    ["Merchant", txn.normalized_merchant ?? "—"],
    ["Recurring", txn.is_recurring ? "Yes" : "No"],
  ];

  return (
    <aside className="w-[320px] shrink-0 border-l border-rule pl-6 ml-6 sticky top-0 self-start py-1">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="t-label mb-2">Transaction</div>
          <Money amount={txn.amount} type={txn.transaction_type} pending={txn.is_pending} size="lg" />
        </div>
        <button onClick={onClose} aria-label="Close details"
          className="t-body text-ink-faint hover:text-ink leading-none">×</button>
      </div>

      <dl className="flex flex-col">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 py-2 rule-b">
            <dt className="t-label shrink-0">{label}</dt>
            <dd className="t-small text-right truncate">{value}</dd>
          </div>
        ))}
      </dl>

      <details className="mt-5">
        <summary className="t-small text-ink-muted cursor-pointer hover:text-ink list-none">
          <span className="text-accent">▸</span> Source record
        </summary>
        <pre className="mt-2 t-num-sm text-ink-faint whitespace-pre-wrap break-all
                        bg-ink/[0.03] p-3 leading-relaxed">
{JSON.stringify(
  { transaction_id: txn.transaction_id, description: txn.description,
    plaid_category_primary: txn.plaid_category_primary, amount: txn.amount },
  null, 2,
)}
        </pre>
      </details>

      <div className="mt-5 flex flex-col gap-2 items-start">
        <button className="t-small text-accent hover:underline">Change category</button>
        <button className="t-small text-accent hover:underline">Mark as transfer</button>
        <button className="t-small text-accent hover:underline">Create rule from this</button>
      </div>
    </aside>
  );
}
