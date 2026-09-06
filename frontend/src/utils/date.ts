/** Date helpers. All ledger dates are calendar dates with no timezone —
 *  parse them as local, never through `new Date(isoString)` which shifts by
 *  the UTC offset and can move a transaction to the previous day. */

export function parseLedgerDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

/** Serialize a Date to the calendar-date form the API expects. Built from the
 *  LOCAL fields — `toISOString()` converts to UTC first and can hand back
 *  yesterday for anyone west of Greenwich. */
export function toISODate(date: Date): string {
  const m = `${date.getMonth() + 1}`.padStart(2, "0");
  const d = `${date.getDate()}`.padStart(2, "0");
  return `${date.getFullYear()}-${m}-${d}`;
}

export function formatDate(iso: string): string {
  return parseLedgerDate(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

export function formatDateLong(iso: string): string {
  return parseLedgerDate(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatMonth(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, 1).toLocaleDateString("en-US", { month: "short" });
}

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const mins = Math.floor((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
