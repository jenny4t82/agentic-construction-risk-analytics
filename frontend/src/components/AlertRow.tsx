import { Check, CircleX, ShieldCheck } from 'lucide-react';
import type { ReactNode } from 'react';
import type { AlertDetailResponse, AlertStatus } from '../types';

type ActionStatus = Extract<AlertStatus, 'acknowledged' | 'resolved' | 'dismissed'>;
const formatTime = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));

export function AlertRow({ alert, canManage, busy, onStatus }: {
  alert: AlertDetailResponse; canManage: boolean; busy: boolean; onStatus: (alert: AlertDetailResponse, status: ActionStatus) => void;
}) {
  const actions: { status: ActionStatus; label: string; icon: ReactNode }[] = [
    { status: 'acknowledged', label: 'Acknowledge', icon: <Check size={14} /> },
    { status: 'resolved', label: 'Resolve', icon: <ShieldCheck size={14} /> },
    { status: 'dismissed', label: 'Dismiss', icon: <CircleX size={14} /> },
  ];
  const timestamps = [['Acknowledged', alert.acknowledged_at], ['Resolved', alert.resolved_at], ['Dismissed', alert.dismissed_at]] as const;
  return <article className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h4 className="font-semibold capitalize text-slate-900">{alert.alert_type.replaceAll('_', ' ')}</h4><p className="mt-1 text-sm text-slate-600">Alert #{alert.alert_id} · {alert.risk_band ?? 'Unclassified'} snapshot · <span className="capitalize">{alert.status}</span></p><p className="mt-1 text-xs text-slate-500">{alert.message} · Assessment #{alert.assessment_id ?? 'unknown'}</p></div><div className="flex flex-wrap gap-2">{canManage && actions.filter((action) => action.status !== alert.status && !['resolved', 'dismissed'].includes(alert.status)).map((action) => <button type="button" key={action.status} disabled={busy} onClick={() => onStatus(alert, action.status)} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-2.5 py-1.5 text-xs font-semibold hover:border-teal-600 disabled:opacity-50">{action.icon}{action.label}</button>)}</div></div>
    {alert.review_required && <p role="status" className="mt-3 rounded-lg bg-amber-50 p-2.5 text-xs text-amber-900">Assessment correction requires review. Historical alert snapshot remains {alert.risk_band ?? 'unclassified'}; current assessment is {alert.current_assessment?.risk_band ?? alert.current_assessment?.status ?? 'unavailable'}. Lifecycle remains {alert.status}.</p>}
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500"><span>Alert created {formatTime(alert.created_at)}</span>{timestamps.filter(([, value]) => value).map(([label, value]) => <span key={label}>{label} {formatTime(value!)}</span>)}</div>
  </article>;
}
