/**
 * API client. Thin — no caching layer, no query library.
 *
 * Money always crosses the wire as a STRING and is never parsed into a JS
 * number except for display formatting. Financial arithmetic happens on the
 * backend (SPEC §3): the frontend displays results, it does not compute them.
 */

import type { Account, CashFlowReport } from "@/types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

// Held module-level and attached by `request`, so no call site has to remember
// the header. Set by AuthProvider whenever the session changes.
let authToken: string | null = null;

export function setAuthToken(token: string | null): void {
  authToken = token;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly detail?: Record<string, unknown>,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        ...init?.headers,
      },
    });
  } catch (cause) {
    // Network-level failure: show the real reason, never "Something went
    // wrong" (DESIGN.md §3.8).
    throw new ApiError(0, "network_error", "Could not reach the server.", {
      cause: String(cause),
    });
  }

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(
      response.status,
      body.error ?? "unknown_error",
      body.detail ?? body.hint ?? body.error ?? `Request failed (${response.status})`,
      body,
    );
  }
  return body as T;
}

export interface AccountsResponse {
  accounts: Account[];
  net_worth: string;
  count: number;
}

export interface PlaidItem {
  item_id: string;
  institution_id: string | null;
  institution_name: string | null;
  status: string;
  last_synced_at: string | null;
  created_at: string;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; expires_at: number; username: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  getSession: () => request<{ username: string; valid: boolean }>("/auth/session"),

  getAccounts: () => request<AccountsResponse>("/accounts"),

  /** Cash-flow report, Sankey-shaped. Aggregation happens in Athena; the
   *  frontend lays the result out and does not recompute any total. */
  getCashFlowReport: (from: string, to: string) =>
    request<CashFlowReport>(
      `/reports/cash-flow?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`,
    ),

  getItems: () => request<{ items: PlaidItem[] }>("/plaid/items"),

  createLinkToken: () =>
    request<{ link_token: string; expiration: string; mode: string }>("/plaid/link-token", {
      method: "POST",
      body: JSON.stringify({}),
    }),

  /** `force` adds a second login at an already-connected institution. Without
   *  it the backend returns 409 rather than silently duplicating every account
   *  and double-counting net worth. */
  exchangePublicToken: (publicToken: string, force = false) =>
    request<{
      item_id: string;
      institution_name: string | null;
      accounts_added: number;
      relinked: boolean;
    }>("/plaid/exchange", {
      method: "POST",
      body: JSON.stringify({ public_token: publicToken, force }),
    }),
};
