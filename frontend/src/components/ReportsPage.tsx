import { useEffect, useState, type FormEvent } from 'react';
import { Download, FileText, RefreshCw } from 'lucide-react';
import { downloadSafetyReport, fetchReportWorkAreas, fetchSafetyReport } from '../api/client';
import type { SafetyReport, SafetyReportFilters } from '../types';
import { formatConfidence, formatDateTime, formatHazardType } from '../utils/formatters';

const metricLabels: { key: keyof SafetyReport['summary']; label: string }[] = [
  { key: 'total_observations', label: 'Total observations' },
  { key: 'supported_ppe_findings', label: 'Supported PPE findings' },
  { key: 'actionable_alerts', label: 'Actionable alerts' },
  { key: 'warnings', label: 'Warnings' },
  { key: 'pending_assessments', label: 'Pending assessments' },
  { key: 'resolved_alerts', label: 'Resolved alerts' },
];

export function ReportsPage() {
  const [areas, setAreas] = useState<string[]>([]);
  const [areaError, setAreaError] = useState<string | null>(null);
  const [startInput, setStartInput] = useState('');
  const [endInput, setEndInput] = useState('');
  const [scope, setScope] = useState<'all' | 'selected'>('all');
  const [selectedAreas, setSelectedAreas] = useState<string[]>([]);
  const [includeUnassigned, setIncludeUnassigned] = useState(false);
  const [report, setReport] = useState<SafetyReport | null>(null);
  const [appliedFilters, setAppliedFilters] = useState<SafetyReportFilters | null>(null);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshAreas = async () => {
    setAreaError(null);
    try {
      const names = await fetchReportWorkAreas();
      setAreas(names);
      setSelectedAreas((current) => current.filter((name) => names.includes(name)));
      setReport(null); setAppliedFilters(null);
    }
    catch (reason) { setAreaError(reason instanceof Error ? reason.message : 'Unable to load named work areas'); }
  };
  useEffect(() => {
    void fetchReportWorkAreas().then(setAreas).catch((reason: unknown) => {
      setAreaError(reason instanceof Error ? reason.message : 'Unable to load named work areas');
    });
  }, []);
  const invalidate = () => { setReport(null); setAppliedFilters(null); setError(null); };
  const toggleArea = (name: string) => {
    setSelectedAreas((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name]);
    invalidate();
  };

  const preview = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const start = startInput ? new Date(startInput) : null;
    const end = endInput ? new Date(endInput) : null;
    if ((start && Number.isNaN(start.getTime())) || (end && Number.isNaN(end.getTime())) || (start && end && start >= end)) {
      setError('Enter a valid period with the start earlier than the end.'); return;
    }
    if (scope === 'selected' && selectedAreas.length === 0 && !includeUnassigned) {
      setError('Select at least one named work area or include unassigned observations.'); return;
    }
    const filters: SafetyReportFilters = {
      start: start?.toISOString(), end: end?.toISOString(), scope,
      workAreas: scope === 'selected' ? [...selectedAreas].sort() : [],
      includeUnassigned: scope === 'selected' && includeUnassigned,
    };
    setLoading(true); setError(null); setReport(null);
    try { setReport(await fetchSafetyReport(filters)); setAppliedFilters(filters); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to generate report'); }
    finally { setLoading(false); }
  };

  const download = async () => {
    if (!appliedFilters) return;
    setDownloading(true); setError(null);
    try { await downloadSafetyReport(appliedFilters); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to download PDF'); }
    finally { setDownloading(false); }
  };

  return <div className="space-y-7">
    <header><p className="text-sm font-bold text-teal-700">Persisted safety records</p><h2 className="mt-1 text-3xl font-bold">Safety Reports</h2><p className="mt-2 text-slate-500">Choose a reporting period and work areas, preview the recorded evidence, then download a PDF.</p></header>

    <form onSubmit={preview} className="panel p-5 sm:p-6 space-y-5">
      <div className="flex items-center gap-2"><FileText size={20} className="text-teal-700" /><h3 className="font-bold text-lg">Report configuration</h3></div>
      <div className="flex flex-wrap gap-4">
        <label className="text-sm font-semibold">Start date/time<input aria-label="Report start date/time" type="datetime-local" value={startInput} onChange={(event) => { setStartInput(event.target.value); invalidate(); }} className="mt-1 block rounded-lg border border-slate-300 p-2 text-sm" /></label>
        <label className="text-sm font-semibold">End date/time<input aria-label="Report end date/time" type="datetime-local" value={endInput} onChange={(event) => { setEndInput(event.target.value); invalidate(); }} className="mt-1 block rounded-lg border border-slate-300 p-2 text-sm" /></label>
      </div>
      <p className="text-xs text-slate-500">Leave both dates blank for all recorded history. Times use your local timezone; start is inclusive and end is exclusive.</p>
      <fieldset className="space-y-3"><legend className="text-sm font-bold">Work Area / Zone</legend>
        <label className="flex items-center gap-2 text-sm"><input type="radio" checked={scope === 'all'} onChange={() => { setScope('all'); invalidate(); }} /> All work areas, including unassigned observations</label>
        <label className="flex items-center gap-2 text-sm"><input type="radio" checked={scope === 'selected'} onChange={() => { setScope('selected'); invalidate(); }} /> Select named work areas</label>
        {scope === 'selected' && <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
          <button type="button" onClick={() => void refreshAreas()} className="flex items-center gap-1 text-xs font-semibold text-teal-700"><RefreshCw size={13} /> Refresh available areas</button>
          {areaError && <p role="alert" className="text-sm text-rose-700">{areaError}</p>}
          {areas.length === 0 && <p className="text-sm text-slate-500">No named work areas have been recorded yet.</p>}
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{areas.map((name) => <label key={name} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selectedAreas.includes(name)} onChange={() => toggleArea(name)} /> {name}</label>)}</div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeUnassigned} onChange={(event) => { setIncludeUnassigned(event.target.checked); invalidate(); }} /> Include unassigned observations</label>
        </div>}
      </fieldset>
      <button type="submit" disabled={loading} className="rounded-lg bg-teal-700 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">{loading ? 'Preparing preview…' : 'Preview report'}</button>
    </form>

    {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">{error}</p>}
    {report && <div className="space-y-6" aria-label="Safety report preview">
      <section className="panel p-5 sm:p-6 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-sm font-bold text-teal-700">SafeSite Risk Intelligence</p><h3 className="text-2xl font-bold">Safety Intelligence Report</h3></div><button type="button" onClick={() => void download()} disabled={downloading} className="flex items-center gap-2 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-bold text-white disabled:opacity-50"><Download size={17} /> {downloading ? 'Generating PDF…' : 'Download PDF'}</button></div>
        <p className="text-sm text-slate-600">Period: {report.scope.window_start || report.scope.window_end ? `${report.scope.window_start ? formatDateTime(report.scope.window_start) : 'beginning'} to before ${report.scope.window_end ? formatDateTime(report.scope.window_end) : 'present'}` : 'All recorded history'}</p>
        <p className="text-sm text-slate-600">Work areas: {report.scope.all_work_areas ? 'All work areas' : [...report.scope.work_areas, ...(report.scope.include_unassigned ? ['Unassigned work area'] : [])].join(', ')}</p>
        <p className="text-xs text-slate-500">Generated {formatDateTime(report.generated_at)} by {report.generated_by.email} ({report.generated_by.role}).</p>
      </section>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{metricLabels.map(({ key, label }) => <div key={key} className="panel p-4"><p className="text-xs font-semibold text-slate-500">{label}</p><p className="mt-1 text-2xl font-bold">{report.summary[key]}</p></div>)}</div>
      {report.summary.total_observations === 0 && <p role="status" className="panel p-5 text-sm text-slate-700">No recorded SafeSite observations match the selected report scope.</p>}
      <section className="panel p-5 space-y-3"><h3 className="font-bold text-lg">Decisions and risk distribution</h3><p className="text-xs text-slate-500">Decision counts are per observation; risk counts are supported finding rows.</p><div className="flex flex-wrap gap-3 text-sm">{Object.entries(report.decision_counts).map(([name, count]) => <span key={name} className="rounded-lg bg-slate-100 px-3 py-2">{name}: {count}</span>)}</div><div className="flex flex-wrap gap-3 text-sm">{Object.entries(report.risk_distribution).map(([name, count]) => <span key={name} className="rounded-lg bg-teal-50 px-3 py-2">{name}: {count}</span>)}</div></section>
      <section className="panel p-5 space-y-2"><h3 className="font-bold text-lg">Supported PPE violations</h3>{report.violation_breakdown.length === 0 ? <p className="text-sm text-slate-500">No supported PPE findings in this scope.</p> : report.violation_breakdown.map((item) => <p key={item.hazard_type} className="text-sm">{formatHazardType(item.hazard_type)}: {item.count}</p>)}</section>
      <section className="panel p-5 space-y-2"><h3 className="font-bold text-lg">Work-area analysis</h3><p className="text-xs text-slate-500">Counts are supported finding rows. Work areas are operator-entered free text.</p>{report.work_areas.map((item) => <p key={item.work_area} className="text-sm">{item.work_area}: {item.violation_count} findings{item.most_common_violation ? ` · most common ${formatHazardType(item.most_common_violation)}` : ''}</p>)}{report.highest_violation_work_areas.length > 0 && <p className="text-sm font-semibold">Highest recorded PPE-violation count (ties shown): {report.highest_violation_work_areas.join(', ')}</p>}</section>
      <section className="panel p-5 space-y-2"><h3 className="font-bold text-lg">Repeated violation observations</h3><p className="text-xs text-slate-500">Informational only; distinct observations in the same named area and canonical hazard group.</p>{report.recurrence.length === 0 ? <p className="text-sm text-slate-500">No repeated named-area PPE groups in this scope.</p> : report.recurrence.map((item) => <p key={`${item.work_area}:${item.hazard_type}`} className="text-sm">{item.work_area} · {formatHazardType(item.hazard_type)}: {item.observation_count} observations ({item.observation_ids.join(', ')})</p>)}</section>
      <section className="panel p-5 space-y-2"><h3 className="font-bold text-lg">Alert lifecycle</h3><p className="text-sm">{Object.entries(report.alert_status_counts).map(([name, count]) => `${name}: ${count}`).join(' · ')}</p>{report.alerts.map((item) => <div key={item.alert_id} className="border-t border-slate-100 pt-2 text-sm">Alert #{item.alert_id} · Observation {item.observation_id} · {item.work_area} · {item.hazard_type ? formatHazardType(item.hazard_type) : 'Finding unavailable'} · {item.risk_band || 'Not scored'} · {item.status}<p className="text-xs text-slate-500">Created {formatDateTime(item.created_at)}{item.acknowledged_at ? ` · Acknowledged ${formatDateTime(item.acknowledged_at)}` : ''}{item.resolved_at ? ` · Resolved ${formatDateTime(item.resolved_at)}` : ''}{item.dismissed_at ? ` · Dismissed ${formatDateTime(item.dismissed_at)}` : ''}</p></div>)}</section>
      <section className="panel p-5 overflow-x-auto"><h3 className="font-bold text-lg mb-3">Detailed supported findings</h3>{report.findings.length === 0 ? <p className="text-sm text-slate-500">No supported findings in this scope.</p> : <table className="w-full text-left text-xs"><thead><tr className="border-b border-slate-200">{['Observation', 'Observed at', 'Work area', 'PPE finding', 'Confidence', 'Risk', 'Decision', 'Alert'].map((label) => <th key={label} className="p-2">{label}</th>)}</tr></thead><tbody>{report.findings.map((item) => <tr key={item.detected_hazard_id} className="border-b border-slate-100"><td className="p-2">{item.observation_id}</td><td className="p-2">{formatDateTime(item.observed_at)}</td><td className="p-2">{item.work_area}</td><td className="p-2">{formatHazardType(item.hazard_type)}</td><td className="p-2">{formatConfidence(item.detection_confidence)}</td><td className="p-2">{item.risk_band ? `${item.risk_band} (${item.risk_score})` : 'Not yet scored'}</td><td className="p-2">{item.safety_decision}</td><td className="p-2">{item.alert_status || '—'}</td></tr>)}</tbody></table>}</section>
      <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-900">{report.disclaimer}</p>
    </div>}
  </div>;
}
