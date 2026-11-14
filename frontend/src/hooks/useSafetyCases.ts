import { useCallback, useEffect, useState } from 'react';
import { fetchSafetyCases } from '../api/client';
import type { SafetyCaseFilters, SafetyCaseListResponse } from '../types';

export function useSafetyCases(filters: SafetyCaseFilters) {
  const [data, setData] = useState<SafetyCaseListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try { setData(await fetchSafetyCases(filters)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load safety cases'); }
    finally { setLoading(false); }
  }, [filters]);
  useEffect(() => {
    let active = true;
    void fetchSafetyCases(filters).then((result) => { if (active) { setData(result); setError(null); } })
      .catch((reason) => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load safety cases'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [filters]);
  return { data, loading, error, refresh, beginLoading: () => setLoading(true) };
}
