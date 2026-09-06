import type { LedgerEntry, Transaction, TransferGroup } from "@/types";

/**
 * Collapse transactions and transfer groups into ledger entries.
 *
 * A matched transfer renders as ONE entry holding both legs, so the pair can be
 * shown cancelling rather than as two unexplained rows (DESIGN.md §3.7A).
 */
export function buildLedger(
  transactions: Transaction[],
  groups: TransferGroup[],
): LedgerEntry[] {
  const byId = new Map(transactions.map((t) => [t.transaction_id, t]));
  const consumed = new Set<string>();
  const entries: LedgerEntry[] = [];

  for (const group of groups) {
    const source = byId.get(group.source_transaction_id);
    const destination = byId.get(group.destination_transaction_id);
    // A group whose other leg is outside the current page would render as half
    // a pair. Skip it — the legs then show as ordinary rows, which is honest.
    if (!source || !destination) continue;
    consumed.add(group.source_transaction_id);
    consumed.add(group.destination_transaction_id);
    entries.push({ kind: "transfer", group, source, destination });
  }

  for (const transaction of transactions) {
    if (consumed.has(transaction.transaction_id)) continue;
    entries.push({ kind: "transaction", transaction });
  }

  return entries.sort((a, b) => {
    const da = a.kind === "transfer" ? a.source.transaction_date : a.transaction.transaction_date;
    const db = b.kind === "transfer" ? b.source.transaction_date : b.transaction.transaction_date;
    return db.localeCompare(da);
  });
}
