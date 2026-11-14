import { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, BarChart3, CalendarDays, MapPinned, RefreshCw, Search, ShieldCheck } from 'lucide-react';
import { fetchZoneAnalytics } from '../api/client';
import type { AnalyticsAreaMetric, SafetyAnalyticsResponse } from '../types';
import { formatHazardType } from '../utils/formatters';
import { ZoneObservationDrawer } from './ZoneObservationDrawer';

type Window = { start?: string; end?: string };
const localStart = (value: string) => value ? new Date(value + 'T00:00:00').toISOString() : undefined;
const localEndExclusive = (value: string) => {
  if (!value) return undefined;
  const date = new Date(value + 'T00:00:00');
  date.setDate(date.getDate() + 1);
  return date.toISOString();
};

export function ZoneAnalyticsPage() {
  const [data, setData] = useState<SafetyAnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadVersion, setReloadVersion] = useState(0);
  const [loadedRequest, setLoadedRequest] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [selectedArea, setSelectedArea] = useState<AnalyticsAreaMetric | null>(null);
  const [drawer, setDrawer] = useState<{ area: string; hazard?: string } | null>(null);
  const rangeInvalid = Boolean(startDate && endDate && startDate > endDate);
  const window = useMemo<Window>(() => ({ start: localStart(startDate), end: localEndExclusive(endDate) }), [startDate, endDate]);
  const requestKey = JSON.stringify([window.start, window.end, reloadVersion]);
  const loading = loadedRequest !== requestKey && !rangeInvalid;
  const errorMessage = rangeInvalid ? 'Start date must be on or before the end date.' : error;
  useEffect(() => {
    if (rangeInvalid) return;
    let active = true;
    void fetchZoneAnalytics(window)
      .then(result => { if (active) { setData(result); setError(null); setLoadedRequest(requestKey); } })
      .catch(reason => { if (active) { setError(reason instanceof Error ? reason.message : 'Unable to load zone analytics'); setLoadedRequest(requestKey); } });
    return () => { active = false; };
  }, [rangeInvalid, requestKey, window]);

  const categories = selectedArea?.violation_metrics ?? [];

  return <main className="space-y-6 sm:space-y-7">
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div><p className="text-sm font-bold text-teal-700">Pattern review</p><h2 className="mt-1 text-3xl font-bold text-slate-900">Zone analytics</h2><p className="mt-2 max-w-3xl text-sm text-slate-600">Investigate persisted PPE findings by work area. Finding frequency and observation risk are reported as separate measures.</p></div>
      <button type="button" onClick={() => setReloadVersion(value => value + 1)} disabled={loading || rangeInvalid} className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-bold text-slate-700 hover:border-teal-400 disabled:opacity-50"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button>
    </header>

    <section className="panel flex flex-wrap items-end gap-3 p-4 sm:p-5" aria-label="Analytics date range">
      <div className="mr-auto"><h3 className="font-bold text-slate-900">Observation date range</h3><p className="mt-1 text-xs text-slate-500">Dates use your local timezone. Start is inclusive; the selected end date is included through local midnight after it.</p></div>
      <label className="grid gap-1 text-xs font-semibold text-slate-600">Start date<input type="date" value={startDate} max={endDate || undefined} onChange={event => setStartDate(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" /></label>
      <label className="grid gap-1 text-xs font-semibold text-slate-600">End date<input type="date" value={endDate} min={startDate || undefined} onChange={event => setEndDate(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" /></label>
      <button type="button" onClick={() => { setStartDate(''); setEndDate(''); }} disabled={!startDate && !endDate} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40">Clear filters</button>
    </section>

    {errorMessage && <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{errorMessage}</div>}
    {loading && <div role="status" className="panel p-8 text-sm text-slate-500">Loading zone analytics…</div>}
    {!rangeInvalid && !loading && data && <>
      <section aria-label="Zone analytics summary" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={MapPinned} label="Work areas" value={data.violations_by_work_area.length} detail="Free-text work-area labels" />
        <Stat icon={Search} label="Unique observations" value={data.unique_observation_count} detail="Distinct persisted observation IDs" />
        <Stat icon={BarChart3} label="Supported hazard findings" value={data.total_violations} detail="Detected-hazard rows; not observations" />
        <Stat icon={ShieldCheck} label="Valid latest assessments" value={data.valid_latest_completed_assessment_count} detail={data.pending_latest_assessment_count + ' pending · ' + data.incomplete_latest_assessment_count + ' incomplete'} />
        <Stat icon={Activity} label="Individual alerts" value={data.individual_alert_count} detail={data.all_unresolved_alert_count + ' unresolved · ' + data.safety_case_count + ' safety cases'} />
        <Stat icon={AlertTriangle} label="Most recorded hazard findings" value={data.highest_violation_area?.work_area ?? '—'} detail={data.highest_violation_area ? data.highest_violation_area.violation_count + ' finding rows' : 'No findings in this range'} />
        <Stat icon={CalendarDays} label="Fewest recorded hazard findings" value={data.lowest_violation_area?.work_area ?? '—'} detail={data.lowest_violation_area ? data.lowest_violation_area.violation_count + ' finding rows' : 'No findings in this range'} />
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <section className="panel overflow-hidden xl:col-span-2" aria-labelledby="zone-compare-title">
          <div className="panel-heading"><div><h3 id="zone-compare-title">Work-area comparison</h3><p>{data.zone_identifier_note} Ranked by supported detected-hazard rows, not risk severity.</p></div><MapPinned className="text-teal-700" size={20} /></div>
          {!data.violations_by_work_area.length ? <div className="p-8 text-center text-sm text-slate-500">No supported findings match this date range.</div> : <div className="overflow-x-auto"><table className="w-full min-w-[840px] text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3 sm:px-6">Work area</th><th className="px-4 py-3">Findings</th><th className="px-4 py-3">Observations</th><th className="px-4 py-3">Overall risk mix · observations</th><th className="px-4 py-3">Assessment states</th><th className="px-4 py-3">Alerts / cases</th><th className="px-4 py-3">Investigation</th></tr></thead><tbody className="divide-y divide-slate-100">{data.violations_by_work_area.map(area => <tr key={area.work_area} className={selectedArea?.work_area === area.work_area ? 'bg-teal-50/70' : ''}><th scope="row" className="px-4 py-4 font-bold text-slate-900 sm:px-6">{area.work_area}</th><td className="px-4 py-4 font-semibold">{area.violation_count}</td><td className="px-4 py-4">{area.observation_count}</td><td className="px-4 py-4 text-xs text-slate-600">{['Critical', 'High', 'Moderate', 'Low', 'pending', 'incomplete'].filter(band => area.overall_observation_risk_distribution[band]).map(band => band + ' ' + area.overall_observation_risk_distribution[band]).join(' · ') || 'No valid risk'}</td><td className="px-4 py-4 text-xs text-slate-600">{area.valid_latest_completed_assessment_count} completed · {area.pending_latest_assessment_count} pending · {area.incomplete_latest_assessment_count} incomplete</td><td className="px-4 py-4 text-xs text-slate-600">{area.individual_alert_count} alerts · {area.safety_case_count} cases</td><td className="px-4 py-4"><button type="button" onClick={() => { setSelectedArea(area); setDrawer({ area: area.work_area }); }} className="rounded-lg border border-teal-200 bg-white px-3 py-2 text-xs font-bold text-teal-800 hover:bg-teal-50 focus-visible:outline-2 focus-visible:outline-teal-700">View findings</button></td></tr>)}</tbody></table></div>}
        </section>

        <section className="panel" aria-labelledby="risk-distribution-title">
          <div className="panel-heading"><div><h3 id="risk-distribution-title">Overall observation risk</h3><p>Unit: distinct observations. Maximum valid latest finding score; provisional observations are marked separately.</p></div><ShieldCheck className="text-teal-700" size={19} /></div>
          <div className="grid grid-cols-2 gap-2 p-4">{Object.entries(data.overall_observation_risk_distribution).map(([band, count]) => <div key={band} className="rounded-xl bg-slate-50 p-3"><p className="text-xs font-semibold capitalize text-slate-600">{band.replaceAll('_', ' ')}</p><p className="mt-1 text-xl font-bold text-slate-900">{count}</p></div>)}<div className="col-span-2 rounded-xl border border-amber-200 bg-amber-50 p-3"><p className="text-xs font-semibold text-amber-900">Provisional overall risk</p><p className="mt-1 text-xl font-bold text-amber-950">{data.provisional_observation_count} observations</p></div></div>
        </section>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className="panel"><div className="panel-heading"><div><h3>Latest finding assessments</h3><p>Legacy distribution unit: supported detected-hazard rows; displayed independently from observation risk above.</p></div></div><div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-5">{Object.entries(data.risk_level_distribution).map(([band, count]) => <div key={band} className="rounded-xl bg-slate-50 p-3"><p className="text-xs capitalize text-slate-600">{band}</p><p className="mt-1 text-lg font-bold text-slate-900">{count}</p></div>)}</div></section>
        <section className="panel"><div className="panel-heading"><div><h3>Individual alert lifecycle</h3><p>Unit: alert IDs linked to supported findings; Open and Acknowledged are unresolved.</p></div></div><div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">{Object.entries(data.alert_status_counts).map(([status, count]) => <div key={status} className="rounded-xl bg-slate-50 p-3"><p className="text-xs capitalize text-slate-600">{status}</p><p className="mt-1 text-lg font-bold text-slate-900">{count}</p></div>)}</div></section>
      </div>

      {selectedArea && <section className="panel p-4 sm:p-5" aria-labelledby="selected-zone-heading"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-teal-700">Selected work area</p><h3 id="selected-zone-heading" className="mt-1 text-xl font-bold text-slate-900">{selectedArea.work_area}</h3><p className="mt-1 text-sm text-slate-600">Choose a supported hazard category to inspect persisted supporting observations.</p></div><button type="button" onClick={() => setSelectedArea(null)} className="rounded-lg px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-100">Clear selection</button></div><div className="mt-4 flex flex-wrap gap-2">{categories.length ? categories.map(({ violation_type: type, count }) => <button key={type} type="button" onClick={() => setDrawer({ area: selectedArea.work_area, hazard: type })} className="rounded-xl border border-teal-200 bg-teal-50 px-3 py-2 text-sm font-semibold text-teal-900 hover:bg-teal-100">{formatHazardType(type)} <span className="ml-1 rounded-full bg-white px-2 py-0.5 text-xs">{count} findings</span></button>) : <p className="text-sm text-slate-500">No supported category data for this area.</p>}</div></section>}
      <p className="text-xs text-slate-500">A work-area label is free text, not a validated zone entity. Frequency describes persisted finding rows; risk classification describes assessment results and does not measure event frequency.</p>
    </>}
    {drawer && <ZoneObservationDrawer area={drawer.area} hazardType={drawer.hazard} window={window} onClose={() => setDrawer(null)} />}
  </main>;
}

function Stat({ icon: Icon, label, value, detail }: { icon: typeof BarChart3; label: string; value: string | number; detail: string }) {
  return <article className="panel min-w-0 p-4 sm:p-5"><div className="flex items-start justify-between gap-2"><span className="text-sm font-semibold text-slate-600">{label}</span><Icon size={18} className="shrink-0 text-teal-700" /></div><p className="mt-4 truncate text-2xl font-bold text-slate-900" title={String(value)}>{value}</p><p className="mt-1 text-xs text-slate-500">{detail}</p></article>;
}