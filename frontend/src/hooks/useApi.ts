import { useState, useEffect, useCallback, useRef } from "react";
import { isLockedError } from "@/api/client";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** `true` when the backend rejected the request with 401/403 — UI shows a gated state. */
  locked: boolean;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [locked, setLocked] = useState(false);
  const mountedRef = useRef(true);

  // Keep the latest fetcher in a ref so fetchData's identity only changes with `deps`.
  // This lets callers pass inline arrow functions without re-running on every render,
  // while still calling the freshest closure.
  const fetcherRef = useRef(fetcher);
  useEffect(() => {
    fetcherRef.current = fetcher;
  }, [fetcher]);

  const fetchData = useCallback(() => {
    setLoading(true);
    setError(null);
    setLocked(false);
    fetcherRef
      .current()
      .then((result) => {
        if (mountedRef.current) {
          setData(result);
        }
      })
      .catch((err: Error) => {
        if (!mountedRef.current) return;
        if (isLockedError(err)) {
          setLocked(true);
        }
        setError(err.message);
      })
      .finally(() => {
        if (mountedRef.current) {
          setLoading(false);
        }
      });
    // `deps` is the caller-controlled dependency array; intentionally spread
    // as-is so exhaustive-deps can still analyse each entry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps]);

  useEffect(() => {
    mountedRef.current = true;
    fetchData();
    return () => {
      mountedRef.current = false;
    };
  }, [fetchData]);

  return { data, loading, error, locked, refetch: fetchData };
}
