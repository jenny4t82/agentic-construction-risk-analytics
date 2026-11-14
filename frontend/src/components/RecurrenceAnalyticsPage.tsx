import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { BarChart3, CalendarClock, MapPinned, RefreshCw, Repeat2, Search } from 'lucide-react';
import { fetchWorkAreaRecurrence } from '../api/client';
import type { WorkAreaRecurrenceGroup, WorkAreaRecurrenceResponse } from '../types';
import { formatDateTime, formatHazardType } from '../utils/formatters';
import type { AppSection } from './AppShell';
import { ZoneObservationDrawer } from './ZoneObservationDrawer';

type Bounds = { start?: string; end?: string };
type GroupSort = 'observations' | 'area' | 'hazard';

export function RecurrenceAnalyticsPage({ onNavigate: _onNavigate }: { onNavigate: (section: AppSection) => void }) {
  const [data, setData] = useState<WorkAreaRecurrenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startInput, setStartInput] = useState('');
  const [endInput, setEndInput] = useState('');
  const [bounds, setBounds] = useState<Bounds>({});
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<GroupSort>('observations');
  const [selected, setSelected] = useState<WorkAreaRecurrenceGroup | null>(null);
  const requestNumber = useRef(0);

  const load = useCallback(async (nextBounds: Bounds) => {
    const request = ++requestNumber.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchWorkAreaRecurrence(nextBounds.start, nextBounds.end);
      if (request === requestNumber.current) setData(result);
    } catch (reason) {
      if (request === requestNumber.current) {
        setData(null);
        setError(reason instanceof Error ? reason.message : 'Unable to load recurrence analytics');
      }
    } finally {
      if (request === requestNumber.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    const request = ++requestNumber.current;
    void fetchWorkAreaRecurrence().then(result => {
      if (active && request === requestNumber.current) setData(result);
    }).catch((reason: unknown) => {
      if (active && request === requestNumber.current) setError(reason instanceof Error ? reason.message : 'Unable to load recurrence analytics');
    }).finally(() => {
      if (active && request === requestNumber.current) setLoading(false);
    });
    return () => { active = false; requestNumber.current += 1; };
  }, []);

  const applyBounds = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const start = startInput ? new Date(startInput) : null;
    const end = endInput ? new Date(endInput) : null;
    if ((start && Number.isNaN(start.getTime())) || (end && Number.isNaN(end.getTime()))) {
      setError('Enter valid start and end date/time values.');
      return;
    }
    if (start && end && start >= end) {
      setError('Start must be earlier than end.');
      return;
    }
    const nextBounds = { start: start?.toISOString(), end: end?.toISOString() };
    setBounds(nextBounds);
    setSelected(null);
    void load(nextBounds);
  };

  const clearBounds = () => {
    setStartInput('');
    setEndInput('');
    setBounds({});
    setSelected(null);
    void load({});
  };

  const groups = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return [...(data?.groups ?? [])]
      .filter(group => !query || group.work_area.toLocaleLowerCase().includes(query) || formatHazardType(group.hazard_type).toLocaleLowerCase().includes(query))
      .sort((a, b) => {
        if (sort === 'area') return a.work_area.localeCompare(b.work_area) || a.hazard_type.localeCompare(b.hazard_type);
        if (sort === 'hazard') return a.hazard_type.localeCompare(b.hazard_type) || a.work_area.localeCompare(b.work_area);
        return b.observation_count - a.observation_count || a.work_area.localeCompare(b.work_area) || a.hazard_type.localeCompare(b.hazard_type);
      });
  }, [data, search, sort]);
  const repeatedCount = data?.groups.filter(group => group.is_repeated).length ?? 0;
  const distinctSupportingObservations = new Set(data?.groups.flatMap(group => group.observation_ids) ?? []).size;
  const categoryCount = new Set(data?.groups.map(group => group.hazard_type) ?? []).size;
  const selectedWindow = { start: data?.window_start ?? undefined, end: data?.window_end ?? undefined };

  return <main className="space-y-6 sm:space-y-7">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-sm font-bold text-teal-700">Historical observation review</p>
        <h2 className="mt-1 text-3xl font-bold text-slate-900">Recurrence analytics</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-600">A recurring result means the same supported PPE hazard category was recorded in the same named work area across at least two distinct observations.</p>
      </div>
      <button type="button" onClick={() => void load(bounds)} disabled={loading} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 hover:border-teal-400 disabled:opacity-60"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button>
    </header>

    <section className="panel space-y-4 p-4 sm:p-5" aria-label="Observation time filter">
      <div className="flex items-center gap-2"><CalendarClock size={18} className="text-teal-700" /><h3 className="font-bold text-slate-900">Observation time window</h3></div>
      <form onSubmit={applyBounds} className="flex flex-wrap items-end gap-3">
        <label className="grid gap-1 text-sm font-semibold text-slate-700">Start date/time<input aria-label="Start date/time" type="datetime-local" value={startInput} onChange={event => setStartInput(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" /></label>
        <label className="grid gap-1 text-sm font-semibold text-slate-700">End date/time<input aria-label="End date/time" type="datetime-local" value={endInput} onChange={event => setEndInput(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" /></label>
        <button type="submit" disabled={loading} className="rounded-lg bg-teal-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">Apply</button>
        <button type="button" onClick={clearBounds} disabled={loading || (!bounds.start && !bounds.end && !startInput && !endInput)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60">Clear filters</button>
      </form>
      <p className="text-xs text-slate-600">Times use your local timezone. Filtering uses observation time with an inclusive start and exclusive end. {data ? (data.window_start || data.window_end ? `Showing ${data.window_start ? formatDateTime(data.window_start) : 'the beginning'} to ${data.window_end ? formatDateTime(data.window_end) : 'the present'} (end excluded).` : 'All history.') : ''}</p>
    </section>

    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
    {loading && <div role="status" className="panel p-8 text-sm text-slate-500">Loading recurrence analytics…</div>}
    {!loading && data && <>
      <section aria-label="Recurrence summary" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Repeat2} label="Recurring area/category pairs" value={repeatedCount} detail="Pairs supported by at least two distinct observations" />
        <Stat icon={MapPinned} label="Work areas with recurrence" value={data.repeated_work_area_count} detail="Named free-text work areas" />
        <Stat icon={BarChart3} label="Distinct supporting observations" value={distinctSupportingObservations} detail="Unique IDs across all listed area/category pairs" />
        <Stat icon={Search} label="Supported PPE categories" value={categoryCount} detail="Categories present in this time window" />
      </section>

      <section className="panel space-y-4 p-4 sm:p-5" aria-labelledby="recurrence-groups-title">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div><h3 id="recurrence-groups-title" className="text-lg font-bold text-slate-900">Area and hazard combinations</h3><p className="mt-1 max-w-3xl text-sm text-slate-600">Counts are distinct persisted observation IDs for one category in one named area. They are frequency measures, not risk scores or worker counts.</p></div>
          <div className="flex flex-wrap gap-2">
            <label className="relative"><span className="sr-only">Search work areas or PPE categories</span><Search aria-hidden="true" size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" /><input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search area or category" className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm sm:w-56" /></label>
            <label className="sr-only" htmlFor="recurrence-sort">Sort combinations</label><select id="recurrence-sort" value={sort} onChange={event => setSort(event.target.value as GroupSort)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="observations">Sort: observation count</option><option value="area">Sort: work area</option><option value="hazard">Sort: hazard category</option></select>
          </div>
        </div>

        {groups.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600">{data.groups.length === 0 ? 'No supported PPE findings were recorded in named work areas for this time window. This does not establish that work areas are safe.' : 'No combinations match this search.'}</div> : <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{groups.map(group => <article key={`${group.work_area}\u0000${group.hazard_type}`} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="break-words text-xs font-bold uppercase tracking-wide text-teal-700">{group.work_area}</p><h4 className="mt-1 text-lg font-bold text-slate-900">{formatHazardType(group.hazard_type)}</h4></div><span className={`shrink-0 rounded-full px-3 py-1 text-xs font-bold ${group.is_repeated ? 'bg-amber-100 text-amber-900' : 'bg-slate-100 text-slate-700'}`}>{group.is_repeated ? 'Repeated' : 'Observed once'}</span></div>
          <p className="mt-3 text-sm text-slate-700"><strong className="text-xl text-slate-900">{group.observation_count}</strong> distinct supporting observation{group.observation_count === 1 ? '' : 's'}</p>
          <p className="mt-1 text-xs text-slate-500">{data.window_start || data.window_end ? 'Within the selected observation-time window.' : 'Across all recorded history.'} This count does not indicate assessment severity or accident probability.</p>
          <button type="button" onClick={() => setSelected(group)} className="mt-4 inline-flex min-h-10 items-center justify-center rounded-lg border border-teal-200 bg-teal-50 px-4 py-2 text-sm font-semibold text-teal-900 hover:bg-teal-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700">Inspect supporting observations</button>
        </article>)}</div>}
      </section>
      <p className="text-xs text-slate-500">{data.work_area_note} Reassessments and multiple detections in one observation do not increase recurrence. Work-area spelling and case remain distinct after trimming surrounding whitespace. Unknown-area placeholders are excluded. Recurrence does not identify workers or establish individual behavior.</p>
    </>}
    {selected && <ZoneObservationDrawer area={selected.work_area} hazardType={selected.hazard_type} areaMode="recurrence" window={selectedWindow} onClose={() => setSelected(null)} expectedObservationCount={selected.observation_count} />}
  </main>;
}

function Stat({ icon: Icon, label, value, detail }: { icon: typeof MapPinned; label: string; value: number; detail: string }) {
  return <article className="panel min-w-0 p-4 sm:p-5"><div className="flex items-start justify-between gap-2"><span className="text-sm font-semibold text-slate-600">{label}</span><Icon size={18} className="shrink-0 text-teal-700" /></div><p className="mt-4 text-2xl font-bold text-slate-900">{value}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></article>;
}
