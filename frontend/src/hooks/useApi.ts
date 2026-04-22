import { useState, useEffect, useCallback, useRef } from "react";

interface UseApiResult<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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
    fetcherRef
      .current()
      .then((result) => {
        if (mountedRef.current) {
          setData(result);
        }
      })
      .catch((err: Error) => {
        if (mountedRef.current) {
          setError(err.message);
        }
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

  return { data, loading, error, refetch: fetchData };
}
