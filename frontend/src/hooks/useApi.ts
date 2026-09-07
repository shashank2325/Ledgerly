import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/api/client";

/**
 * Fetch-on-mount with a shared cache and stale-while-revalidate.
 *
 * WHY THE CACHE EXISTS: react-router unmounts a page component on navigation,
 * so without one, every tab switch re-ran every query from scratch. Switching
 * to Ledger and back to Overview paid the full Athena cost twice — and the
 * numbers had not changed, because nothing changes between page views except a
 * sync.
 *
 * Behaviour on a cache hit: render the cached value IMMEDIATELY, then refetch
 * in the background and swap in the result if it differs. The page is instant
 * and still correct — you never look at stale numbers for longer than one
 * request, and you never look at a skeleton for data already in memory.
 *
 * Deliberately module-level and not a dependency. One user, a handful of
 * endpoints, no cache-invalidation problem worth react-query's size — the
 * invalidation rule here is simply "a sync happened", which `clearApiCache`
 * expresses in one line.
 */

interface Entry {
  value: unknown;
  at: number;
}

const cache = new Map<string, Entry>();

// Long enough that navigating around the app never refetches synchronously,
// short enough that a background refresh keeps things honest. The revalidate
// pass means this is a floor on freshness, not a ceiling.
const FRESH_MS = 60_000;

/** Drop everything. Called after a sync or a mutation, where the server state
 *  has genuinely moved and every cached answer is now wrong. */
export function clearApiCache(): void {
  cache.clear();
}

interface State<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { key?: string } = {},
) {
  // Derived from the deps, so two pages requesting the same filtered view share
  // an entry while a different filter gets its own.
  const key = options.key ?? JSON.stringify(deps);
  const cached = cache.get(key);

  const [state, setState] = useState<State<T>>(() =>
    cached
      ? { data: cached.value as T, loading: false, error: null }
      : { data: null, loading: true, error: null },
  );

  // Survives re-renders so a resolving request can tell whether it is still
  // the one the component wants.
  const currentKey = useRef(key);
  currentKey.current = key;

  const run = useCallback(
    (background = false) => {
      const keyAtStart = key;
      const hit = cache.get(keyAtStart);

      if (hit) {
        // Show it now; correctness comes from the revalidate below.
        setState({ data: hit.value as T, loading: false, error: null });
        if (Date.now() - hit.at < FRESH_MS) return;
        background = true;
      } else if (!background) {
        setState({ data: null, loading: true, error: null });
      }

      fetcher()
        .then((data) => {
          cache.set(keyAtStart, { value: data, at: Date.now() });
          // Ignore a response for a filter the user has already moved on from.
          if (currentKey.current !== keyAtStart) return;
          setState({ data, loading: false, error: null });
        })
        .catch((error) => {
          if (currentKey.current !== keyAtStart) return;
          const apiError =
            error instanceof ApiError
              ? error
              : new ApiError(0, "unknown", String(error?.message ?? error));
          // A failed background refresh must not blank out good cached data —
          // that would turn a transient blip into an error screen.
          setState((previous) =>
            background && previous.data !== null
              ? previous
              : { data: null, loading: false, error: apiError },
          );
        });
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );

  useEffect(() => {
    run();
  }, [run]);

  /** Force a fresh fetch, bypassing and replacing the cached entry. */
  const refetch = useCallback(() => {
    cache.delete(key);
    run();
  }, [key, run]);

  return { ...state, refetch };
}
