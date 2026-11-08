import { useState, type ReactNode } from 'react';
import { Activity, Bell, FileText, LayoutDashboard, LogOut, Menu, ShieldAlert, Sparkles, MapPinned, Repeat2, X } from 'lucide-react';
import type { UserRole } from '../types';
import { BrandLockup } from './BrandLockup';

export type AppSection = 'overview' | 'incidents' | 'alerts' | 'zones' | 'recurrence' | 'analysis' | 'reports';

interface AppShellProps {
  activeSection: AppSection;
  onNavigate: (section: AppSection) => void;
  user: { email: string; role: UserRole };
  onLogout: () => void;
  children: ReactNode;
}

const navItems: { id: AppSection; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard },
  { id: 'analysis', label: 'AI Safety Analysis', icon: Sparkles },
  { id: 'incidents', label: 'Safety Incidents', icon: ShieldAlert },
  { id: 'alerts', label: 'Alert Register', icon: Bell },
  { id: 'zones', label: 'Zone Analytics', icon: MapPinned },
  { id: 'recurrence', label: 'Recurrence Analytics', icon: Repeat2 },
  { id: 'reports', label: 'Reports', icon: FileText },
];

function roleLabel(role: UserRole): string {
  return role === 'safety_officer' ? 'Safety Officer' : role[0].toUpperCase() + role.slice(1);
}

export function AppShell({ activeSection, onNavigate, user, onLogout, children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return <div className="min-h-screen bg-[#f4f7f7] text-slate-900 lg:flex">
    {sidebarOpen && <button aria-label="Close navigation" className="fixed inset-0 bg-slate-950/40 z-30 lg:hidden" onClick={() => setSidebarOpen(false)} />}
    <aside className={`fixed lg:static z-40 inset-y-0 left-0 w-72 bg-[#102f33] text-white flex flex-col transition-transform lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="px-6 h-20 flex items-center justify-between border-b border-white/10"><BrandLockup compact /><button className="lg:hidden text-teal-100" onClick={() => setSidebarOpen(false)} aria-label="Close menu"><X size={20} /></button></div>
      <div className="px-4 py-7"><p className="px-3 text-[10px] uppercase tracking-[.2em] font-bold text-teal-100/45 mb-3">Workspace</p><nav className="space-y-1">{navItems.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { onNavigate(id); setSidebarOpen(false); }} className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm font-semibold transition ${activeSection === id ? 'bg-amber-400 text-[#102f33]' : 'text-teal-50/70 hover:bg-white/10 hover:text-white'}`}><Icon size={18} /><span>{label}</span></button>)}</nav></div>
      <div className="mt-auto p-5"><div className="rounded-2xl bg-white/7 border border-white/10 p-4"><div className="flex items-center gap-2 text-xs text-teal-100/60"><Activity size={14} className="text-emerald-300" /> Persisted records</div><p className="mt-3 text-xs text-teal-100/50 leading-relaxed">Views use saved observations and reviewed alerts.</p></div><p className="text-[10px] text-teal-100/35 mt-5 px-1">Prototype · Human oversight required</p></div>
    </aside>
    <div className="flex-1 min-w-0"><header className="h-20 bg-white border-b border-slate-200 flex items-center justify-between px-5 sm:px-8"><div className="flex items-center gap-3"><button className="lg:hidden p-2 rounded-lg hover:bg-slate-100" onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Menu size={21} /></button><div><p className="text-xs font-bold uppercase tracking-[.17em] text-teal-700">SafeSite workspace</p><h1 className="text-lg sm:text-xl font-bold text-slate-900">{navItems.find((item) => item.id === activeSection)?.label}</h1></div></div><div className="flex items-center gap-3"><div className="hidden sm:block text-right"><p className="text-sm font-bold text-slate-800">{user.email}</p><p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{roleLabel(user.role)}</p></div><div className="w-10 h-10 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center font-bold">{user.email[0]?.toUpperCase()}</div><button onClick={onLogout} className="p-2 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50" title="Sign out" aria-label="Sign out"><LogOut size={18} /></button></div></header><main className="max-w-[1500px] mx-auto p-5 sm:p-8">{children}</main></div>
  </div>;
}
