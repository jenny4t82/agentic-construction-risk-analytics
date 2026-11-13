import { useEffect, useState } from 'react';
import { AlertTriangle, Check, CircleX, RefreshCw, ShieldCheck } from 'lucide-react';
import { ApiError, fetchAlerts, updateAlertStatus } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import type { AlertDetailResponse, AlertStatus } from '../types';
import { formatHazardType } from '../utils/formatters';

const formatHazard = formatHazardType;
const cleanAlertMessage = (value: string) => value.replace(/\s*\(source label:[^)]+\)/i, '');
const formatTime = (value: string) => new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
const canManage = (role: string) => role === 'safety_officer' || role === 'admin';

export function AlertsPage() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState<AlertDetailResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<number | null>(null);

  const load = async () => {
    setLoading(true); setError(null);
    try { setAlerts(await fetchAlerts()); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to load alerts'); }
    finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);

  const changeStatus = async (alert: AlertDetailResponse, status: Extract<AlertStatus, 'acknowledged' | 'resolved' | 'dismissed'>) => {
    setUpdating(alert.alert_id); setError(null);
    try {
      const updated = await updateAlertStatus(alert.alert_id, status);
      setAlerts((current) => current.map((item) => item.alert_id === updated.alert_id ? updated : item));
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 403 ? 'Your role cannot manage alert lifecycle changes.' : reason instanceof Error ? reason.message : 'Alert update failed');
    } finally { setUpdating(null); }
  };

  return <div className="space-y-7"><div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm text-teal-700 font-bold">Operational review</p><h2 className="text-3xl font-bold mt-1">Safety alerts</h2><p className="text-slate-500 mt-2">Persisted violation alerts with their review lifecycle.</p></div><button onClick={() => void load()} className="inline-flex items-center gap-2 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm font-bold text-slate-700 hover:border-teal-400"><RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh</button></div>
    {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
    <section className="panel overflow-hidden"><div className="panel-heading"><div><h3>Alert register</h3><p>Each alert remains linked to its source observation and detected violation.</p></div><ShieldCheck className="text-teal-600" size={20} /></div>
      {loading ? <div className="p-8 text-sm text-slate-400">Loading alerts…</div> : alerts.length === 0 ? <div className="p-8 text-sm text-slate-400">No persisted alerts available yet.</div> : <div className="divide-y divide-slate-100">{alerts.map((alert) => <div key={alert.alert_id} className="p-5 sm:p-6 flex flex-col xl:flex-row xl:items-center justify-between gap-5"><div className="flex gap-4 min-w-0"><div className="w-10 h-10 shrink-0 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center"><AlertTriangle size={18} /></div><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h4 className="font-bold capitalize">{formatHazard(alert.alert_type)}</h4><span className={`status-badge ${alert.status === 'resolved' ? 'status-green' : alert.status === 'open' ? 'status-red' : 'status-amber'}`}>{alert.status}</span></div><p className="text-sm text-slate-500 mt-1">{cleanAlertMessage(alert.message)}</p><p className="text-xs text-slate-400 mt-2">{alert.observation.work_area || 'Unspecified area'} · {formatTime(alert.created_at)} · Observation {alert.observation_id}</p><LifecycleTimes alert={alert} /></div></div>{canManage(user?.role ?? 'user') && alert.status !== 'resolved' && alert.status !== 'dismissed' && <div className="flex flex-wrap gap-2 xl:justify-end"><button disabled={updating === alert.alert_id || alert.status === 'acknowledged'} onClick={() => void changeStatus(alert, 'acknowledged')} className="lifecycle-button"><Check size={14} /> Acknowledge</button><button disabled={updating === alert.alert_id} onClick={() => void changeStatus(alert, 'resolved')} className="lifecycle-button lifecycle-success"><ShieldCheck size={14} /> Resolve</button><button disabled={updating === alert.alert_id} onClick={() => void changeStatus(alert, 'dismissed')} className="lifecycle-button lifecycle-danger"><CircleX size={14} /> Dismiss</button></div>}</div>)}</div>}
    </section>
  </div>;
}

function LifecycleTimes({ alert }: { alert: AlertDetailResponse }) {
  const events = [
    ['Acknowledged', alert.acknowledged_at],
    ['Resolved', alert.resolved_at],
    ['Dismissed', alert.dismissed_at],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));
  return <div>
    {alert.review_required && <p role="status" className="mt-2 text-sm text-amber-800">Review required: assessment context was corrected. Historical alert: {alert.risk_band}; current assessment: {alert.current_assessment?.risk_band ?? 'Pending'}. Alert lifecycle is unchanged.</p>}
    <p className="mt-2 text-xs text-slate-500">{events.map(([label, timestamp]) => <span key={label} className="mr-3 inline-block">{label}: {formatTime(timestamp)}</span>)}</p>
  </div>;
}
