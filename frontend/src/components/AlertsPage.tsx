import { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { ApiError, fetchReportWorkAreas, fetchSafetyCase, updateAlertStatus } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import type { AlertDetailResponse, SafetyCaseFilters, SafetyCaseResponse, SafetyCaseStatus } from '../types';
import { SafetyCaseCardList } from './SafetyCaseCardList';
import { SafetyCaseDetailDrawer } from './SafetyCaseDetailDrawer';
import { SafetyCaseFilterBar } from './SafetyCaseFilterBar';
import { SafetyCaseSummary } from './SafetyCaseSummary';
import { useSafetyCases } from '../hooks/useSafetyCases';

interface Props { onNavigate: (section: 'overview' | 'incidents' | 'alerts' | 'zones' | 'recurrence' | 'analysis' | 'reports') => void }
const canManage = (role: string | undefined) => role === 'safety_officer' || role === 'admin';
const dateStart = (value: string) => value ? `${value}T00:00:00.000Z` : undefined;
const dateEnd = (value: string) => {
  if (!value) return undefined;
  const nextDay = new Date(`${value}T00:00:00.000Z`);
  nextDay.setUTCDate(nextDay.getUTCDate() + 1);
  return nextDay.toISOString();
};

export function AlertsPage({ onNavigate }: Props) {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [workArea, setWorkArea] = useState('');
  const [status, setStatus] = useState<SafetyCaseStatus | ''>('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [sort, setSort] = useState<'newest' | 'oldest'>('newest');
  const [limit, setLimit] = useState(20);
  const [offset, setOffset] = useState(0);
  const [workAreas, setWorkAreas] = useState<string[]>([]);
  const [selectedCase, setSelectedCase] = useState<SafetyCaseResponse | null>(null);
  const [busyAlertId, setBusyAlertId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const filters = useMemo<SafetyCaseFilters>(() => ({
    search: search.trim() || undefined, work_area: workArea || undefined, status: status || undefined,
    start: dateStart(startDate), end: dateEnd(endDate), sort, limit, offset,
  }), [search, workArea, status, startDate, endDate, sort, limit, offset]);
  const { data, loading, error, refresh, beginLoading } = useSafetyCases(filters);
  const closeSelectedCase = useCallback(() => setSelectedCase(null), []);

  useEffect(() => { void fetchReportWorkAreas().then(setWorkAreas).catch(() => setWorkAreas([])); }, []);
  useEffect(() => {
    let active = true;
    let requestedId: string | null = null;
    const openTarget = () => {
      const [route, query = ''] = window.location.hash.slice(1).split('?');
      const observationId = route === 'alerts' ? new URLSearchParams(query).get('observation_id') : null;
      if (!observationId) {
        requestedId = null;
        setSelectedCase(null);
        setActionError(null);
        return;
      }
      if (observationId === requestedId) return;
      requestedId = observationId;
      setDetailLoading(true); setActionError(null);
      void fetchSafetyCase(observationId).then(item => { if (active) setSelectedCase(item); })
        .catch(reason => { if (active) { setSelectedCase(null); setActionError(reason instanceof Error ? reason.message : 'Unable to load the linked safety case'); } })
        .finally(() => { if (active) setDetailLoading(false); });
    };
    openTarget();
    window.addEventListener('hashchange', openTarget);
    return () => { active = false; window.removeEventListener('hashchange', openTarget); };
  }, []);
  const resetPage = () => { beginLoading(); setOffset(0); };

  const openCase = async (item: SafetyCaseResponse) => {
    setSelectedCase(item);
    setDetailLoading(true);
    setActionError(null);
    try { setSelectedCase(await fetchSafetyCase(item.observation_id)); }
    catch (reason) { setSelectedCase(null); setActionError(reason instanceof Error ? reason.message : 'Unable to load case details'); }
    finally { setDetailLoading(false); }
  };

  const changeAlertStatus = useCallback(async (alert: AlertDetailResponse, nextStatus: 'acknowledged' | 'resolved' | 'dismissed') => {
    setBusyAlertId(alert.alert_id);
    setActionError(null);
    try {
      // Every action targets one persisted child alert. Refresh both list totals and
      // detail from the backend so the derived case state cannot become stale.
      await updateAlertStatus(alert.alert_id, nextStatus);
      await refresh();
      if (selectedCase) setSelectedCase(await fetchSafetyCase(selectedCase.observation_id));
    } catch (reason) {
      setActionError(reason instanceof ApiError && reason.status === 403
        ? 'Your role cannot manage alert lifecycle changes.'
        : reason instanceof Error ? reason.message : 'Alert update failed');
    } finally { setBusyAlertId(null); }
  }, [refresh, selectedCase]);

  const totalPages = Math.max(1, Math.ceil((data?.total_cases ?? 0) / limit));
  const currentPage = Math.floor(offset / limit) + 1;

  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-bold text-teal-700">Operational review</p><h2 className="mt-1 text-3xl font-bold text-slate-900">Safety Case Register</h2><p className="mt-2 max-w-3xl text-sm text-slate-600">Related alerts are grouped by observation for investigation. Existing alert records and their individual lifecycle remain unchanged.</p></div><div className="flex flex-wrap gap-2"><button type="button" onClick={() => onNavigate('incidents')} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:border-teal-400">Observation History</button><button type="button" onClick={() => void refresh()} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 hover:border-teal-400 disabled:opacity-50"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button></div></header>
    <SafetyCaseSummary data={data} />
    <SafetyCaseFilterBar search={search} onSearch={(value) => { resetPage(); setSearch(value); }} workArea={workArea} onWorkArea={(value) => { resetPage(); setWorkArea(value); }} workAreas={workAreas} status={status} onStatus={(value) => { resetPage(); setStatus(value); }} startDate={startDate} onStartDate={(value) => { resetPage(); setStartDate(value); }} endDate={endDate} onEndDate={(value) => { resetPage(); setEndDate(value); }} sort={sort} onSort={(value) => { resetPage(); setSort(value); }} />
    {(error || actionError) && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{actionError || error}</div>}
    <section aria-label="Safety case results" aria-busy={loading}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600"><p>{data ? `Showing ${data.total_cases === 0 ? 0 : offset + 1}–${Math.min(offset + (data.items.length), data.total_cases)} of ${data.total_cases} cases · ${data.total_alerts} individual alerts` : error ? 'Safety case results unavailable' : 'Loading safety case totals'}</p><label className="flex items-center gap-2">Cases per page<select aria-label="Cases per page" value={limit} onChange={(event) => { resetPage(); setLimit(Number(event.target.value)); }} className="rounded-md border border-slate-300 bg-white px-2 py-1"><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label></div>
      {loading && !data ? <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">Loading safety cases…</p>
        : data?.items.length ? <SafetyCaseCardList items={data.items} onOpen={(item) => void openCase(item)} />
        : !error && <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center"><AlertTriangle className="mx-auto text-slate-400" /><p className="mt-2 font-semibold text-slate-700">No matching safety cases</p><p className="mt-1 text-sm text-slate-500">Try changing the filters or search term.</p></div>}
      <div className="mt-4 flex items-center justify-end gap-3 text-sm"><span>Page {currentPage} of {totalPages}</span><button type="button" disabled={offset === 0 || loading} onClick={() => { beginLoading(); setOffset(Math.max(0, offset - limit)); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 disabled:opacity-40">Previous</button><button type="button" disabled={loading || offset + limit >= (data?.total_cases ?? 0)} onClick={() => { beginLoading(); setOffset(offset + limit); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 disabled:opacity-40">Next</button></div>
    </section>
    {selectedCase && <SafetyCaseDetailDrawer item={selectedCase} canManage={canManage(user?.role)} busyAlertId={busyAlertId} onClose={closeSelectedCase} onAlertStatus={(alert, next) => void changeAlertStatus(alert, next)} />}
    {detailLoading && <p role="status" className="sr-only">Loading complete case details</p>}
  </div>;
}
