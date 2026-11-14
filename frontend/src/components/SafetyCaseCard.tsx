import { AlertCircle, ArrowRight, Clock3, ShieldAlert } from 'lucide-react';
import type { SafetyCaseResponse } from '../types';
import { ObservationThumbnail } from './ObservationThumbnail';

const dateTime = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
const bandClass: Record<string, string> = {
  Critical: 'bg-rose-100 text-rose-900 border-rose-300', High: 'bg-orange-100 text-orange-900 border-orange-300',
  Moderate: 'bg-amber-100 text-amber-900 border-amber-300', Low: 'bg-emerald-100 text-emerald-900 border-emerald-300',
};

export function SafetyCaseCard({ item, onOpen }: { item: SafetyCaseResponse; onOpen: () => void }) {
  const score = item.overall_risk_score == null || !item.overall_risk_band
    ? item.overall_risk_status === 'pending' ? 'Pending' : 'No assessed PPE risk'
    : `${item.overall_risk_band} · ${item.overall_risk_score}`;
  return <article className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm">
    <div className="flex min-w-0 flex-col gap-4 sm:flex-row sm:items-center">
      <ObservationThumbnail observationId={item.observation_id} size="md" />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-bold text-slate-900">Safety case</h3>
          <span className="rounded-full border border-slate-300 bg-slate-50 px-2.5 py-1 text-xs font-semibold capitalize text-slate-700">{item.case_status.replace('_', ' ')}</span>
          <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${bandClass[item.overall_risk_band ?? ''] ?? 'border-slate-300 bg-slate-50 text-slate-700'}`}>Overall risk: {score}</span>
          {item.overall_risk_provisional && <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900">Provisional</span>}
          {item.review_required && <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900"><AlertCircle size={13} /> Review required</span>}
        </div>
        <p className="mt-1 break-all font-mono text-xs text-slate-500">{item.case_id}</p>
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-slate-600"><span>{item.work_area || 'Unspecified work area'}</span><span>{dateTime(item.observed_at)}</span><span>{item.alert_count} individual alert{item.alert_count === 1 ? '' : 's'}</span><span className="inline-flex items-center gap-1"><Clock3 size={14} />{item.unresolved_alert_count} unresolved</span></p>
        <p className="mt-1 text-xs text-slate-500">Open {item.alert_status_counts.open} · Acknowledged {item.alert_status_counts.acknowledged} · Resolved {item.alert_status_counts.resolved} · Dismissed {item.alert_status_counts.dismissed}</p>
        <p className="mt-1 inline-flex items-center gap-1 text-xs text-slate-500"><ShieldAlert size={13} /> Risk classification is separate from each child alert lifecycle.</p>
      </div>
      <button type="button" onClick={onOpen} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-teal-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700">Investigate <ArrowRight size={16} /></button>
    </div>
  </article>;
}
