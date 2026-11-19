import { useCallback, useEffect, useMemo, useState } from "react";
import { api, formatError, Page } from "./api";

export function useList<T = any>(path: string, params: Record<string, any> = {}, enabled = true) {
  const [data, setData] = useState<Page<T> | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const key = path + JSON.stringify(params);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    api
      .get<Page<T>>(path, params)
      .then(setData)
      .catch((e) => setError(formatError(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (enabled) reload();
  }, [reload, enabled]);

  return { data, loading, error, reload };
}

/** Loads up to 100 rows of a reference list and exposes an id -> display name map. */
export function useLookup(path: string, params: Record<string, any> = {}, field = "name") {
  const { data, reload } = useList<any>(path, { limit: 100, ...params });
  const items = data?.items ?? [];
  const names = useMemo(() => {
    const map: Record<number, string> = {};
    items.forEach((item) => (map[item.id] = item[field]));
    return map;
  }, [data]);
  return { items, names, reload };
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
