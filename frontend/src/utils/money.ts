/**
 * Money formatting — implements DESIGN.md §3.4.
 *
 * Rules encoded here:
 *  - units recede: the currency symbol and the cents render faint and smaller
 *    so the magnitude reads first
 *  - round in summaries, exact in the ledger; never round where a user might
 *    be reconciling
 *  - the sign carries the meaning, color only confirms it (never color alone)
 */

export interface MoneyParts {
  sign: string; // "" | "+" | "−" | "→"
  symbol: string; // "$"
  whole: string; // "1,284"
  fraction: string; // ".30"  (empty when rounded)
}

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  GBP: "£",
  CAD: "$",
};

export function currencySymbol(code: string): string {
  return CURRENCY_SYMBOLS[code] ?? `${code} `;
}

/**
 * Split an amount into renderable parts.
 *
 * @param amount  decimal string from the API (never a JS number)
 * @param opts.exact   show cents. True in the ledger, false in summaries.
 * @param opts.signed  render a leading + for inflows (income)
 * @param opts.arrow   render → instead of a sign (transfers)
 * @param opts.forceSign  render BOTH + and − explicitly. Used where two
 *   amounts must be seen to cancel — the expanded transfer pair. The normal
 *   bare-outflow convention would make the two legs look identical.
 */
export function formatMoney(
  amount: string,
  opts: {
    currency?: string;
    exact?: boolean;
    signed?: boolean;
    arrow?: boolean;
    forceSign?: boolean;
  } = {},
): MoneyParts {
  const {
    currency = "USD",
    exact = true,
    signed = false,
    arrow = false,
    forceSign = false,
  } = opts;

  const value = Number.parseFloat(amount);
  const safe = Number.isFinite(value) ? value : 0;
  const magnitude = Math.abs(safe);

  let sign = "";
  // U+2212 MINUS SIGN, not a hyphen — it matches the width and weight of the
  // plus and sits on the same optical axis.
  if (forceSign) sign = safe < 0 ? "\u2212" : "+";
  else if (arrow) sign = "→";
  else if (signed && safe > 0) sign = "+";
  // Outflows render bare. A minus sign on every expense is visual noise in a
  // ledger where most rows are expenses; the column context carries it.

  const whole = Math.floor(exact ? magnitude : Math.round(magnitude)).toLocaleString("en-US");
  const fraction = exact ? `.${magnitude.toFixed(2).split(".")[1]}` : "";

  return { sign, symbol: currencySymbol(currency), whole, fraction };
}

/** Plain string form — for aria-labels, titles, and tests. */
export function moneyToString(amount: string, currency = "USD"): string {
  const value = Number.parseFloat(amount);
  const safe = Number.isFinite(value) ? value : 0;
  return `${safe < 0 ? "-" : ""}${currencySymbol(currency)}${Math.abs(safe).toFixed(2)}`;
}

export function parseAmount(amount: string): number {
  const value = Number.parseFloat(amount);
  return Number.isFinite(value) ? value : 0;
}
