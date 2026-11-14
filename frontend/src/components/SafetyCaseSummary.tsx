import { AlertTriangle, CheckCircle2, Clock3, ShieldAlert } from 'lucide-react';
import type { ReactNode } from 'react';
import type { SafetyCaseListResponse } from '../types';

export function SafetyCaseSummary({ data }: { data: SafetyCaseListResponse | null }) {
  const cases = data?.total_cases ?? '—';
  const alerts = data?.total_alerts ?? '—';
  const unresolved = data ? data.items.reduce((sum, item) => sum + item.unresolved_alert_count, 0) : '—';
  const review = data ? data.items.filter((item) => item.review_required).length : '—';
  return <section aria-label="Safety case summary" className="grid grid-cols-2 xl:grid-cols-4 gap-3">
    <Metric icon={<ShieldAlert size={17} />} label="Matching Cases" value={cases} />
    <Metric icon={<AlertTriangle size={17} />} label="Individual Alerts" value={alerts} />
    <Metric icon={<Clock3 size={17} />} label="Unresolved on this page" value={unresolved} />
    <Metric icon={<CheckCircle2 size={17} />} label="Review required on this page" value={review} />
  </section>;
}

function Metric({ icon, label, value }: { icon: ReactNode; label: string; value: number | string }) {
  return <div className="rounded-xl border border-slate-200 bg-white p-4"><div className="flex items-center gap-2 text-slate-500 text-xs font-semibold">{icon}{label}</div><p className="mt-2 text-2xl font-bold text-slate-900">{value}</p></div>;
}
