import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/api/client";

interface State<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
}

/** Minimal fetch-on-mount hook. No react-query — one user, a handful of
 *  endpoints, and no cache-invalidation problem worth a dependency
 *  (DESIGN.md §3: avoid unnecessary frontend infrastructure). */
export function useApi<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });

  const run = useCallback(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    fetcher()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => {
        if (cancelled) return;
        const apiError =
          error instanceof ApiError
            ? error
            : new ApiError(0, "unknown", String(error?.message ?? error));
        setState({ data: null, loading: false, error: apiError });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(run, [run]);

  return { ...state, refetch: run };
}
