import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowUpRight, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { fetchFindingObservations } from '../api/client';
import type { FindingObservationListResponse } from '../types';
import { formatHazardType } from '../utils/formatters';
import { incidentLink } from '../utils/incidentNavigation';
import { useModalFocus } from '../utils/useModalFocus';
import { ObservationEvidenceViewer } from './ObservationEvidenceViewer';
import { ObservationThumbnail } from './ObservationThumbnail';

interface Props {
  area: string;
  hazardType?: string;
  window: { start?: string; end?: string };
  onClose: () => void;
}

export function ZoneObservationDrawer({ area, hazardType, window, onClose }: Props) {
  const [data, setData] = useState<FindingObservationListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [limit, setLimit] = useState(10);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadedRequest, setLoadedRequest] = useState('');
  const requestKey = JSON.stringify([area, hazardType, window.start, window.end, limit, offset]);
  const loading = loadedRequest !== requestKey;
  const currentData = loadedRequest === requestKey ? data : null;
  const dialogRef = useRef<HTMLDivElement>(null);
  useModalFocus(true, dialogRef, onClose);

  useEffect(() => {
    let active = true;
    void fetchFindingObservations({ work_area: area, hazard_type: hazardType, start: window.start, end: window.end, area_mode: 'zone', sort: 'newest', limit, offset })
      .then(result => { if (active) { setData(result); setError(null); setLoadedRequest(requestKey); } })
      .catch(reason => { if (active) { setData(null); setError(reason instanceof Error ? reason.message : 'Unable to load supporting observations'); setLoadedRequest(requestKey); } });
    return () => { active = false; };
  }, [area, hazardType, window.start, window.end, limit, offset, requestKey]);

  const pages = useMemo(() => Math.max(1, Math.ceil((currentData?.total_observations ?? 0) / limit)), [currentData, limit]);
  const page = Math.floor(offset / limit) + 1;
  const title = hazardType ? formatHazardType(hazardType) + ' findings' : 'Supported findings';
  return <div className="fixed inset-0 z-40 bg-slate-950/45" data-modal-backdrop onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="zone-observations-title" tabIndex={-1} className="absolute inset-y-0 right-0 flex w-full max-w-3xl flex-col overflow-hidden bg-slate-50 shadow-2xl">
      <header className="flex items-start justify-between gap-4 border-b border-slate-200 bg-white p-4 sm:p-6">
        <div className="min-w-0"><p className="text-xs font-bold uppercase tracking-wider text-teal-700">Evidence-linked findings</p><h2 id="zone-observations-title" className="mt-1 break-words text-xl font-bold text-slate-900 sm:text-2xl">{title} · {area}</h2><p className="mt-2 text-sm text-slate-600">One row per persisted observation. Matching finding rows are listed within each observation.</p></div>
        <button type="button" onClick={onClose} aria-label="Close supporting observations" className="shrink-0 rounded-lg p-2 text-slate-600 hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-teal-700"><X size={20} /></button>
      </header>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 sm:px-6"><p>{currentData ? currentData.total_observations + ' observations · ' + currentData.total_matching_findings + ' matching findings' : 'Loading totals'}</p><label className="flex items-center gap-2">Per page<select value={limit} onChange={event => { setOffset(0); setLimit(Number(event.target.value)); }} className="rounded-lg border border-slate-300 px-2 py-1"><option value={10}>10</option><option value={20}>20</option><option value={50}>50</option></select></label></div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4 sm:p-6">
        {loading && !currentData && <p role="status" className="rounded-xl bg-white p-6 text-sm text-slate-500">Loading supporting observations…</p>}
        {error && <p role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</p>}
        {!loading && currentData?.items.length === 0 && <div className="rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-600">No observations match this work area and category.</div>}
        <div className="space-y-3">{currentData?.items.map(item => {
          const matches = item.detected_hazards.filter(hazard => item.matching_detected_hazard_ids.includes(hazard.detected_hazard_id ?? -1));
          return <article key={item.observation_id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex gap-3"><ObservationThumbnail observationId={item.observation_id} size="md" /><div className="min-w-0 flex-1"><a href={incidentLink(item.observation_id)} className="break-all text-sm font-bold text-teal-900 underline">{item.observation_id}</a><p className="mt-1 text-xs text-slate-500">{new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.observed_at))} · {item.work_area || 'Unspecified work area'}</p><div className="mt-2 flex flex-wrap gap-2"><span className={'rounded-full px-2.5 py-1 text-xs font-bold ' + (item.overall_risk_band ? 'bg-rose-50 text-rose-800' : 'bg-slate-100 text-slate-700')}>{item.overall_risk_band ? 'Overall ' + item.overall_risk_band + ' · ' + item.overall_risk_score : item.overall_risk_status === 'pending' ? 'Overall Pending' : 'No confirmed overall score'}</span>{item.overall_risk_provisional && <span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-900">Provisional · {item.pending_assessment_count} pending</span>}</div></div></div>
            <ul className="mt-3 space-y-2">{matches.map(hazard => { const history = [...hazard.assessments].sort((a, b) => b.assessment_version - a.assessment_version); const latest = history[0]; return <li key={hazard.detected_hazard_id} className="rounded-lg bg-slate-50 p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold text-slate-800">{formatHazardType(hazard.hazard_type)}</span><span className="text-xs text-slate-600">{latest?.status === 'completed' && latest.risk_score != null ? latest.risk_band + ' · ' + latest.risk_score : 'Pending or incomplete'}</span>{latest?.assessment_id && <a className="inline-flex items-center gap-1 text-xs font-semibold text-teal-800 underline" href={incidentLink(item.observation_id, latest.assessment_id)}>Open latest assessment <ArrowUpRight size={13} /></a>}</div>{history.length > 0 && <details className="mt-2 border-t border-slate-200 pt-2"><summary className="cursor-pointer text-xs font-semibold text-slate-700">Assessment history ({history.length})</summary><ol className="mt-2 space-y-1">{history.map(assessment => <li key={assessment.assessment_id ?? assessment.assessment_version} className="flex flex-wrap justify-between gap-2 text-xs text-slate-600"><span>v{assessment.assessment_version} · {assessment.status}</span><span>{assessment.risk_score == null ? 'No confirmed score' : assessment.risk_band + ' · ' + assessment.risk_score}</span>{assessment.assessment_id && <a className="text-teal-800 underline" href={incidentLink(item.observation_id, assessment.assessment_id)}>Open assessment #{assessment.assessment_id}</a>}</li>)}</ol></details>}</li>; })}</ul>
            <div className="mt-3 flex flex-wrap gap-3"><button type="button" onClick={() => setExpandedId(expandedId === item.observation_id ? null : item.observation_id)} aria-expanded={expandedId === item.observation_id} className="text-xs font-semibold text-slate-700 underline">{expandedId === item.observation_id ? 'Hide evidence' : 'View original and annotated evidence'}</button><a href={incidentLink(item.observation_id)} className="text-xs font-semibold text-teal-800 underline">Open in Safety Incidents</a>{item.safety_case_id && <a href={'#alerts?observation_id=' + encodeURIComponent(item.observation_id)} className="text-xs font-semibold text-teal-800 underline">Open safety case</a>}</div>
            {expandedId === item.observation_id && <div className="mt-4 border-t border-slate-100 pt-4"><ObservationEvidenceViewer observationId={item.observation_id} /></div>}
          </article>;
        })}</div>
      </div>
      <footer className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-3 text-sm sm:px-6"><button type="button" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40"><ChevronLeft size={16} /> Previous</button><span>Page {page} of {pages}</span><button type="button" disabled={loading || offset + limit >= (currentData?.total_observations ?? 0)} onClick={() => setOffset(offset + limit)} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 disabled:opacity-40">Next <ChevronRight size={16} /></button></footer>
    </section>
  </div>;
}
