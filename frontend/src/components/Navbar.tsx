import React from 'react';
import { HardHat, Activity, Database } from 'lucide-react';

interface NavbarProps {
  isBackendHealthy: boolean;
  isDatabaseConfigured: boolean;
  activeTab: 'dashboard' | 'history';
  setActiveTab: (tab: 'dashboard' | 'history') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  isBackendHealthy,
  isDatabaseConfigured,
  activeTab,
  setActiveTab,
}) => {
  return (
    <header className="bg-slate-900 text-white border-b border-slate-800 sticky top-0 z-50 shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and Brand */}
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-500">
              <HardHat className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">
                  SafeSite Risk Intelligence
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">
                Agentic Construction Risk Analytics Platform
              </p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center space-x-2 sm:space-x-4">
            <button
              onClick={() => setActiveTab('dashboard')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'dashboard'
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              Risk Assessment
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === 'history'
                  ? 'bg-slate-800 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              Observation History
            </button>
          </div>

          {/* System Status Indicators */}
          <div className="hidden md:flex items-center space-x-3">
            {/* Backend API status */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                isBackendHealthy
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
              }`}
              title={isBackendHealthy ? 'API is healthy' : 'API is disconnected'}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>{isBackendHealthy ? 'API Active' : 'API Offline'}</span>
            </div>

            {/* Database status */}
            <div
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${
                isDatabaseConfigured
                  ? 'bg-blue-500/10 border-blue-500/30 text-blue-400'
                  : 'bg-slate-800 border-slate-700 text-slate-400'
              }`}
              title={
                isDatabaseConfigured
                  ? 'PostgreSQL persistence is active'
                  : 'Stateless mode (DATABASE_URL unset)'
              }
            >
              <Database className="w-3.5 h-3.5" />
              <span>{isDatabaseConfigured ? 'PostgreSQL Active' : 'Stateless Mode'}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
