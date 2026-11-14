import { Search } from 'lucide-react';
import type { SafetyCaseStatus } from '../types';

interface Props {
  search: string; onSearch: (value: string) => void;
  workArea: string; onWorkArea: (value: string) => void; workAreas: string[];
  status: SafetyCaseStatus | ''; onStatus: (value: SafetyCaseStatus | '') => void;
  startDate: string; onStartDate: (value: string) => void;
  endDate: string; onEndDate: (value: string) => void;
  sort: 'newest' | 'oldest'; onSort: (value: 'newest' | 'oldest') => void;
}

export function SafetyCaseFilterBar(props: Props) {
  const input = 'min-w-0 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm';
  return <section aria-label="Filter safety cases" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-6 gap-3 rounded-xl border border-slate-200 bg-white p-4">
    <label className="xl:col-span-2 text-xs font-semibold text-slate-600">Search case or observation ID
      <span className="mt-1 flex items-center gap-2 rounded-lg border border-slate-300 px-3"><Search size={15} aria-hidden="true" /><input className="w-full min-w-0 py-2 text-sm outline-none" value={props.search} onChange={(event) => props.onSearch(event.target.value)} placeholder="observation ID" /></span>
    </label>
    <label className="text-xs font-semibold text-slate-600">Work area<select className={`${input} mt-1`} value={props.workArea} onChange={(event) => props.onWorkArea(event.target.value)}><option value="">All work areas</option>{props.workAreas.map((area) => <option key={area}>{area}</option>)}</select></label>
    <label className="text-xs font-semibold text-slate-600">Case status<select className={`${input} mt-1`} value={props.status} onChange={(event) => props.onStatus(event.target.value as SafetyCaseStatus | '')}><option value="">All statuses</option><option value="open">Open</option><option value="acknowledged">Acknowledged</option><option value="resolved">Resolved</option><option value="dismissed">Dismissed</option><option value="mixed_closed">Mixed closed</option></select></label>
    <label className="text-xs font-semibold text-slate-600">Observed from<input aria-label="Observed from" type="date" className={`${input} mt-1`} value={props.startDate} onChange={(event) => props.onStartDate(event.target.value)} /></label>
    <label className="text-xs font-semibold text-slate-600">Observed through<input aria-label="Observed through" type="date" className={`${input} mt-1`} value={props.endDate} onChange={(event) => props.onEndDate(event.target.value)} /></label>
    <label className="text-xs font-semibold text-slate-600">Sort<select className={`${input} mt-1`} value={props.sort} onChange={(event) => props.onSort(event.target.value as 'newest' | 'oldest')}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label>
  </section>;
}
