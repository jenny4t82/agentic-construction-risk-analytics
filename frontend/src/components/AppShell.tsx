import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useModalFocus } from '../utils/useModalFocus';
import { Activity, Bell, ChevronLeft, ChevronRight, FileText, LayoutDashboard, LogOut, Menu, ShieldAlert, Sparkles, MapPinned, Repeat2, X } from 'lucide-react';
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

const COLLAPSED_STORAGE_KEY = 'safesite.sidebar_collapsed';

export function AppShell({ activeSection, onNavigate, user, onLogout, children }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktop, setDesktop] = useState(() => window.matchMedia('(min-width: 1024px)').matches);
  const sidebarRef = useRef<HTMLElement>(null);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  useModalFocus(sidebarOpen && !desktop, sidebarRef, closeSidebar);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 1024px)');
    const changed = () => { setDesktop(media.matches); setSidebarOpen(false); };
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    try {
      return window.sessionStorage.getItem(COLLAPSED_STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });

  const toggleCollapsed = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        window.sessionStorage.setItem(COLLAPSED_STORAGE_KEY, String(next));
      } catch {
        // sessionStorage might be restricted
      }
      return next;
    });
  };

  return (
    <div className="min-h-screen bg-[#f4f7f7] text-slate-900 lg:flex">
      {sidebarOpen && (
        <button
          aria-label="Close navigation"
          data-modal-backdrop
          tabIndex={-1}
          className="fixed inset-0 bg-slate-950/40 z-30 lg:hidden cursor-default"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        ref={sidebarRef}
        id="workspace-navigation"
        inert={!desktop && !sidebarOpen}
        role={!desktop && sidebarOpen ? 'dialog' : undefined}
        aria-modal={!desktop && sidebarOpen ? true : undefined}
        aria-label="Workspace navigation"
        tabIndex={-1}
        className={`fixed lg:static z-40 inset-y-0 left-0 bg-[#102f33] text-white flex flex-col transition-[width,transform] duration-200 ease-in-out motion-reduce:transition-none ${
          isCollapsed ? 'lg:w-20' : 'lg:w-72'
        } w-72 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        {/* Sidebar Brand Header */}
        <div
          className={`h-20 flex items-center border-b border-white/10 px-4 sm:px-5 ${
            isCollapsed ? 'lg:justify-center' : 'justify-between'
          }`}
        >
          <div className="flex items-center gap-3">
            <BrandLockup compact iconOnly={isCollapsed} />
          </div>

          {/* Desktop collapse toggle button inside sidebar header */}
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!isCollapsed}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className={`hidden ${
              isCollapsed ? 'lg:hidden' : 'lg:flex'
            } items-center justify-center p-1.5 rounded-lg text-teal-100/70 hover:text-white hover:bg-white/10 transition-colors focus:outline-hidden focus:ring-2 focus:ring-amber-400`}
          >
            <ChevronLeft size={18} />
          </button>

          {/* Mobile close button */}
          <button
            type="button"
            className="lg:hidden text-teal-100 p-1.5 rounded-lg hover:bg-white/10"
            onClick={() => setSidebarOpen(false)}
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Collapsed Mode Expand Button */}
        {isCollapsed && (
          <div className="hidden lg:flex justify-center pt-3 pb-1 px-3">
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label="Expand sidebar"
              aria-expanded={false}
              title="Expand sidebar"
              className="w-10 h-10 flex items-center justify-center rounded-xl text-teal-100/70 hover:text-white hover:bg-white/10 transition-colors focus:outline-hidden focus:ring-2 focus:ring-amber-400"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        )}

        {/* Navigation */}
        <div className="px-3 sm:px-4 py-5 flex-1 overflow-y-auto">
          <p
            className={`px-3 text-[10px] uppercase tracking-[.2em] font-bold text-teal-100/45 mb-3 ${
              isCollapsed ? 'lg:hidden' : ''
            }`}
          >
            Workspace
          </p>
          <nav className="space-y-1.5">
            {navItems.map(({ id, label, icon: Icon }) => {
              const isActive = activeSection === id;
              return (
                <button
                  key={id}
                  onClick={() => {
                    onNavigate(id);
                    setSidebarOpen(false);
                  }}
                  title={label}
                  aria-label={label}
                  className={`w-full flex items-center ${
                    isCollapsed ? 'lg:justify-center lg:px-0' : 'gap-3 px-3'
                  } py-3 rounded-xl text-sm font-semibold transition ${
                    isActive
                      ? 'bg-amber-400 text-[#102f33] shadow-xs'
                      : 'text-teal-50/70 hover:bg-white/10 hover:text-white'
                  } focus:outline-hidden focus:ring-2 focus:ring-amber-400`}
                >
                  <Icon size={19} className="shrink-0" />
                  <span className={`truncate ${isCollapsed ? 'lg:hidden' : ''}`}>{label}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Footer info card */}
        <div className="p-4 mt-auto">
          {/* Expanded mode footer */}
          <div className={isCollapsed ? 'lg:hidden' : 'block'}>
            <div className="rounded-2xl bg-white/7 border border-white/10 p-4">
              <div className="flex items-center gap-2 text-xs text-teal-100/60 font-medium">
                <Activity size={14} className="text-emerald-300 shrink-0" />
                <span>Persisted records</span>
              </div>
              <p className="mt-2 text-xs text-teal-100/50 leading-relaxed">
                Views use saved observations and reviewed alerts.
              </p>
            </div>
            <p className="text-[10px] text-teal-100/35 mt-3 px-1">Prototype · Human oversight required</p>
          </div>

          {/* Collapsed mode footer indicator */}
          <div className={`hidden ${isCollapsed ? 'lg:flex' : ''} justify-center`}>
            <div
              className="w-10 h-10 rounded-xl bg-white/7 border border-white/10 flex items-center justify-center text-emerald-300 hover:bg-white/10 cursor-help transition"
              title="Persisted records · Views use saved observations and reviewed alerts. Prototype · Human oversight required"
              aria-label="Persisted records info"
            >
              <Activity size={18} />
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 transition-all duration-200 ease-in-out motion-reduce:transition-none flex flex-col">
        {/* Application Header */}
        <header className="h-20 bg-white border-b border-slate-200 flex items-center justify-between px-5 sm:px-8 shrink-0">
          <div className="flex items-center gap-3">
            {/* Mobile menu toggle */}
            <button
              className="lg:hidden p-2 rounded-lg hover:bg-slate-100 text-slate-700"
              onClick={() => setSidebarOpen(true)}
              aria-label="Open navigation"
              aria-expanded={sidebarOpen}
              aria-controls="workspace-navigation"
            >
              <Menu size={21} />
            </button>

            {/* Desktop collapse toggle in header */}
            <button
              type="button"
              className="hidden lg:flex p-2 rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors"
              onClick={toggleCollapsed}
              title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <Menu size={20} />
            </button>

            <div>
              <p className="text-xs font-bold uppercase tracking-[.17em] text-teal-700">SafeSite workspace</p>
              <h1 className="text-lg sm:text-xl font-bold text-slate-900">
                {navItems.find((item) => item.id === activeSection)?.label}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-right">
              <p className="text-sm font-bold text-slate-800">{user.email}</p>
              <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{roleLabel(user.role)}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center font-bold">
              {user.email[0]?.toUpperCase()}
            </div>
            <button
              onClick={onLogout}
              className="p-2 text-slate-400 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition-colors"
              title="Sign out"
              aria-label="Sign out"
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>

        {/* Content body */}
        <main className="max-w-[1500px] w-full mx-auto p-5 sm:p-8 flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}
