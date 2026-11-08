import { useEffect, useRef, useState, type FormEvent } from 'react';
import { BarChart3, Clock3, MapPinned, RefreshCw, Repeat2 } from 'lucide-react';
import { fetchWorkAreaRecurrence } from '../api/client';
import type { WorkAreaRecurrenceResponse } from '../types';
import { formatDateTime, formatHazardType } from '../utils/formatters';
import type { AppSection } from './AppShell';

type Bounds = { start?: string; end?: string };

export function RecurrenceAnalyticsPage({ onNavigate }: { onNavigate: (section: AppSection) => void }) {
  const [data, setData] = useState<WorkAreaRecurrenceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startInput, setStartInput] = useState('');
  const [endInput, setEndInput] = useState('');
  const [bounds, setBounds] = useState<Bounds>({});
  const requestNumber = useRef(0);

  const load = async (nextBounds: Bounds) => {
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
  };

  useEffect(() => {
    const request = ++requestNumber.current;
    void fetchWorkAreaRecurrence().then((result) => {
      if (request === requestNumber.current) setData(result);
    }).catch((reason: unknown) => {
      if (request === requestNumber.current) setError(reason instanceof Error ? reason.message : 'Unable to load recurrence analytics');
    }).finally(() => {
      if (request === requestNumber.current) setLoading(false);
    });
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
    void load(nextBounds);
  };

  const clearBounds = () => {
    setStartInput('');
    setEndInput('');
    setBounds({});
    void load({});
  };

  const repeatedGroups = data?.groups.filter((group) => group.is_repeated) ?? [];
  const highestGroup = repeatedGroups[0]; // The backend orders by count, then area and hazard type.
  const rankedRecurringAreas = data?.work_areas_by_observation_count.filter((area) => repeatedGroups.some((group) => group.work_area === area.work_area)) ?? [];

  return <div className="space-y-7">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="text-sm text-teal-700 font-bold">Historical observation review</p>
        <h2 className="text-3xl font-bold mt-1">Recurrence analytics</h2>
        <p className="text-slate-500 mt-2">Repeated supported PPE violations across distinct recorded observations in named work areas.</p>
      </div>
      <button type="button" onClick={() => void load(bounds)} disabled={loading} className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-bold text-slate-700 hover:border-teal-400 disabled:opacity-60"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button>
    </div>

    <section className="panel p-5 sm:p-6 space-y-4" aria-label="Observation time filter">
      <div className="flex items-center gap-2"><Clock3 size={18} className="text-teal-700" /><h3 className="font-bold">Observation time window</h3></div>
      <form onSubmit={applyBounds} className="flex flex-wrap items-end gap-3">
        <label className="text-sm font-semibold text-slate-700">Start date/time
          <input aria-label="Start date/time" type="datetime-local" value={startInput} onChange={(event) => setStartInput(event.target.value)} className="block mt-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" />
        </label>
        <label className="text-sm font-semibold text-slate-700">End date/time
          <input aria-label="End date/time" type="datetime-local" value={endInput} onChange={(event) => setEndInput(event.target.value)} className="block mt-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900" />
        </label>
        <button type="submit" disabled={loading} className="px-4 py-2 rounded-lg bg-teal-700 text-white text-sm font-semibold disabled:opacity-60">Apply</button>
        <button type="button" onClick={clearBounds} disabled={loading} className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold text-slate-700 disabled:opacity-60">Clear</button>
      </form>
      <p className="text-sm text-slate-600">{data ? (data.window_start || data.window_end ? `Showing observations from ${data.window_start ? formatDateTime(data.window_start) : 'the beginning'} up to, but not including, ${data.window_end ? formatDateTime(data.window_end) : 'the present'}.` : 'All history — no date filter applied.') : (bounds.start || bounds.end ? 'Loading selected time window.' : 'All history — no date filter applied.')}</p>
      <p className="text-xs text-slate-500">Times entered here use your local timezone. Filtering uses observation time; the start is inclusive and the end is exclusive.</p>
    </section>

    {error && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    {loading && <div role="status" className="panel p-8 text-sm text-slate-500">Loading recurrence analytics…</div>}
    {!loading && data && <>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Stat icon={MapPinned} label="Work areas with recurrence" value={data.repeated_work_area_count} detail="Named areas with at least one repeated PPE finding" />
        <Stat icon={Repeat2} label="Recurring PPE groups" value={repeatedGroups.length} detail="Area and canonical PPE violation pairs" />
        <Stat icon={BarChart3} label="Highest group count" value={highestGroup?.observation_count ?? 0} detail={highestGroup ? `${highestGroup.work_area} · ${formatHazardType(highestGroup.hazard_type)}` : 'No repeated group in this window'} />
      </div>

      <section className="panel overflow-hidden">
        <div className="panel-heading"><div><h3>Work areas with recurring PPE findings</h3><p>Areas with at least one repeated group, ranked by the backend's distinct-observation count for any supported PPE violation. Counts can also include other findings.</p></div><MapPinned size={20} className="text-teal-600" /></div>
        {rankedRecurringAreas.length === 0 ? <p className="p-6 text-sm text-slate-500">No work area has a repeated PPE finding in this time window.</p> : <ol className="divide-y divide-slate-100">{rankedRecurringAreas.map((area, index) => <li key={area.work_area} className="flex flex-wrap items-center justify-between gap-3 px-6 py-4 text-sm"><div><span className="text-slate-400 mr-3">{index + 1}.</span><strong className="text-slate-800">{area.work_area}</strong></div><span className="font-semibold text-slate-700">{area.observation_count} distinct observation{area.observation_count === 1 ? '' : 's'}</span></li>)}</ol>}
      </section>

      <section className="space-y-4" aria-label="PPE violation observation groups">
        <div><h3 className="text-xl font-bold">PPE violation groups</h3><p className="text-sm text-slate-500 mt-1">Two or more distinct observations of the same supported PPE violation in one named work area are marked repeated.</p></div>
        {data.groups.length === 0 ? <div className="panel p-8 text-sm text-slate-600">No supported PPE-violation observations were recorded in named work areas for this time window. This does not establish that work areas are safe.</div> : data.groups.map((group) => <article key={`${group.work_area}\u0000${group.hazard_type}`} className="panel p-5 sm:p-6 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-teal-700">{group.work_area}</p><h4 className="text-lg font-bold text-slate-900 mt-1">{formatHazardType(group.hazard_type)}</h4></div><span className={`rounded-full px-3 py-1 text-xs font-bold ${group.is_repeated ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-600'}`}>{group.is_repeated ? 'Repeated' : 'Observed once'}</span></div>
          <p className="text-sm text-slate-700"><strong>{group.observation_count}</strong> distinct observation{group.observation_count === 1 ? '' : 's'}</p>
          <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Contributing observation IDs</p><div className="mt-2 flex flex-wrap gap-2">{group.observation_ids.map((id) => <code key={id} className="rounded-lg bg-slate-100 px-2.5 py-1.5 text-xs text-slate-700 break-all">{id}</code>)}</div></div>
          <button type="button" onClick={() => onNavigate('incidents')} className="text-sm font-semibold text-teal-700 underline">View Observation History</button>
        </article>)}
      </section>
      <p className="text-xs text-slate-500">{data.work_area_note} Names keep their spelling and case. Counts describe recorded observations, not workers, accidents, or risk scores. Rejected exact-image retries add no observation. This view does not change assessments or alerts.</p>
    </>}
  </div>;
}

function Stat({ icon: Icon, label, value, detail }: { icon: typeof MapPinned; label: string; value: number; detail: string }) {
  return <div className="panel p-5"><div className="flex justify-between gap-3"><span className="text-sm font-semibold text-slate-500">{label}</span><Icon size={18} className="text-teal-600 shrink-0" /></div><p className="text-2xl font-bold mt-5">{value}</p><p className="text-xs text-slate-500 mt-1">{detail}</p></div>;
}
