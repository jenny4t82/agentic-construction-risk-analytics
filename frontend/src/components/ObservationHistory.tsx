import { useCallback, useEffect, useId, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpDown,
  Calendar,
  CheckCircle2,
  Clock,
  Database,
  Filter,
  History,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  X,
} from 'lucide-react';
import {
  ApiError,
  fetchAssessmentContext,
  fetchObservationDetail,
  fetchReportWorkAreas,
  queryObservations,
} from '../api/client';
import type {
  AssessmentFilter,
  ObservationDetailResponse,
  ObservationFilters,
  ObservationQueryResponse,
} from '../types';
import { incidentTarget } from '../utils/incidentNavigation';
import { ObservationRow } from './ObservationRow';

interface Props {
  onNavigate?: (section: 'overview' | 'incidents' | 'alerts' | 'zones' | 'recurrence' | 'analysis' | 'reports') => void;
  onRefresh?: () => void;
  onAssessmentCompleted?: (observationId: string) => void;
  onWorkAreaUpdated?: (observation: ObservationDetailResponse) => void;
  // Backward compatibility props:
  observations?: ObservationDetailResponse[];
  isLoading?: boolean;
  isDatabaseConfigured?: boolean;
  error?: string | null;
}

const RISK_TABS: { id: AssessmentFilter; label: string }[] = [
  { id: 'All', label: 'All' },
  { id: 'Pending', label: 'Pending' },
  { id: 'Critical', label: 'Critical' },
  { id: 'High', label: 'High' },
  { id: 'Moderate', label: 'Moderate' },
  { id: 'Low', label: 'Low' },
];

export function ObservationHistory({
  onNavigate,
  onRefresh: parentOnRefresh,
  onAssessmentCompleted: parentOnAssessmentCompleted,
  onWorkAreaUpdated: parentOnWorkAreaUpdated,
}: Props) {
  // Query Filters state
  const [selectedRisk, setSelectedRisk] = useState<AssessmentFilter>('All');
  const [searchId, setSearchId] = useState('');
  const [selectedArea, setSelectedArea] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest');
  const [pageSize, setPageSize] = useState<number>(20);
  const [pageOffset, setPageOffset] = useState<number>(0);

  // Data state
  const [queryResult, setQueryResult] = useState<ObservationQueryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDbConfigured, setIsDbConfigured] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [workAreas, setWorkAreas] = useState<string[]>([]);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(() => new Date());

  // Direct-link / Expand state
  const [expandedId, setExpandedId] = useState<string | null>(() => incidentTarget().observationId);
  const [targetAssessmentId, setTargetAssessmentId] = useState<string | null>(() => incidentTarget().assessmentId);
  const [directLinkObs, setDirectLinkObs] = useState<ObservationDetailResponse | null>(null);
  const [directLinkError, setDirectLinkError] = useState<string | null>(null);

  const searchInputId = useId();
  const workAreaSelectId = useId();
  const startDateInputId = useId();
  const endDateInputId = useId();
  const sortSelectId = useId();

  // Load available work areas
  useEffect(() => {
    let active = true;
    void fetchReportWorkAreas()
      .then((areas) => {
        if (active) setWorkAreas(areas);
      })
      .catch(() => {
        // Fallback silently if unavailable
      });
    return () => {
      active = false;
    };
  }, []);

  // Main data query function
  const executeQuery = useCallback(async (background = false) => {
    if (!background) setIsLoading(true);
    setErrorMessage(null);

    const apiFilters: ObservationFilters = {
      risk: selectedRisk,
      sort: sortOrder,
      limit: pageSize,
      offset: pageOffset,
    };

    if (searchId.trim()) {
      apiFilters.observation_id = searchId.trim();
    }
    if (selectedArea.trim()) {
      apiFilters.work_area = selectedArea.trim();
    }
    if (startDate) {
      // Backend requires timezone-bearing ISO datetime string
      apiFilters.start = new Date(startDate).toISOString();
    }
    if (endDate) {
      apiFilters.end = new Date(endDate).toISOString();
    }

    try {
      const res = await queryObservations(apiFilters);
      setQueryResult(res);
      setIsDbConfigured(true);
      setLastRefreshed(new Date());
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to query safety incidents';
      if (msg.includes('503') || msg.toLowerCase().includes('database is not configured')) {
        setIsDbConfigured(false);
      } else {
        setErrorMessage(msg);
      }
    } finally {
      setIsLoading(false);
    }
  }, [selectedRisk, searchId, selectedArea, startDate, endDate, sortOrder, pageSize, pageOffset]);

  // Load data on filter change
  useEffect(() => {
    void executeQuery();
  }, [executeQuery]);

  // Handle direct-link navigation from hash (#incidents?observation_id=...&assessment_id=...)
  useEffect(() => {
    let generation = 0;
    const handleHash = async () => {
      const request = ++generation;
      const target = incidentTarget();
      setDirectLinkObs(null);
      setDirectLinkError(null);
      setExpandedId(null);
      setTargetAssessmentId(null);
      if (target.observationId) {
          try {
            const obs = await fetchObservationDetail(target.observationId);
            if (request !== generation) return;
            setDirectLinkObs(obs);
            setExpandedId(target.observationId);
            if (target.assessmentId) {
              const belongs = obs.detected_hazards.some(h => h.assessments.some(a => String(a.assessment_id) === target.assessmentId));
              if (!belongs) {
                if (!/^[1-9]\d*$/.test(target.assessmentId)) throw new Error(`Assessment "${target.assessmentId}" was not found.`);
                try {
                  await fetchAssessmentContext(Number(target.assessmentId));
                } catch (err) {
                  if (err instanceof ApiError && err.status === 404) throw new Error(`Assessment "${target.assessmentId}" was not found.`);
                  throw err;
                }
                throw new Error(`Assessment "${target.assessmentId}" belongs to another observation and cannot be focused here.`);
              }
              setTargetAssessmentId(target.assessmentId);
            }
          } catch (err) {
            if (request !== generation) return;
            setDirectLinkError(
              `Direct-link observation "${target.observationId}" could not be loaded: ${
                err instanceof Error ? err.message : 'Not found'
              }`
            );
          }
      } else if (target.assessmentId) {
        setDirectLinkError('An observation ID is required to open this assessment.');
      }
    };

    void handleHash();
    window.addEventListener('hashchange', handleHash);
    return () => { generation++; window.removeEventListener('hashchange', handleHash); };
  }, []);

  const returnToHistory = () => {
    const params = new URLSearchParams(window.location.hash.split('?')[1] ?? '');
    params.delete('observation_id');
    params.delete('assessment_id');
    window.location.hash = `incidents${params.size ? `?${params}` : ''}`;
  };

  // Scroll to and highlight targeted assessment once expanded
  useEffect(() => {
    if (targetAssessmentId && expandedId) {
      const timer = setTimeout(() => {
        const el = document.getElementById(`assessment-${targetAssessmentId}`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.focus();
        }
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [targetAssessmentId, expandedId, queryResult, directLinkObs]);

  // Clear all filters
  const clearFilters = () => {
    setSelectedRisk('All');
    setSearchId('');
    setSelectedArea('');
    setStartDate('');
    setEndDate('');
    setSortOrder('newest');
    setPageOffset(0);
  };

  const hasActiveFilters =
    selectedRisk !== 'All' ||
    searchId.trim() !== '' ||
    selectedArea !== '' ||
    startDate !== '' ||
    endDate !== '' ||
    sortOrder !== 'newest';

  // Toggle item expansion
  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  // Handle successful assessment update / completion
  const handleAssessmentUpdated = (observationId: string) => {
    void executeQuery(true);
    if (directLinkObs?.observation_id === observationId) {
      void fetchObservationDetail(observationId).then(setDirectLinkObs).catch(() => {
        setDirectLinkError('Assessment saved; refresh to reload the linked observation.');
      });
    }
    parentOnAssessmentCompleted?.(observationId);
  };

  // Handle work area update
  const handleWorkAreaUpdated = (updated: ObservationDetailResponse) => {
    setQueryResult((current) => {
      if (!current) return current;
      return {
        ...current,
        items: current.items.map((item) =>
          item.observation_id === updated.observation_id
            ? { ...item, ...updated }
            : item
        ),
      };
    });
    if (directLinkObs?.observation_id === updated.observation_id) {
      setDirectLinkObs(updated);
    }
    parentOnWorkAreaUpdated?.(updated);
  };

  // Compile list of displayed items
  const displayItems = queryResult?.items ?? [];
  const supplemental = directLinkObs && !displayItems.some(item => item.observation_id === directLinkObs.observation_id);

  // Calculate metrics derived from real backend API counts
  const totalObservations = queryResult?.unfiltered_risk_total ?? 0;
  const pendingAssessments = queryResult?.assessment_counts?.Pending ?? 0;
  const highCriticalFindings =
    (queryResult?.assessment_counts?.High ?? 0) + (queryResult?.assessment_counts?.Critical ?? 0);
  const completedAssessments =
    (queryResult?.assessment_counts?.Low ?? 0) +
    (queryResult?.assessment_counts?.Moderate ?? 0) +
    (queryResult?.assessment_counts?.High ?? 0) +
    (queryResult?.assessment_counts?.Critical ?? 0);

  // Pagination calculation
  const totalMatching = queryResult?.total ?? 0;
  const currentStart = totalMatching === 0 ? 0 : pageOffset + 1;
  const currentEnd = Math.min(pageOffset + pageSize, totalMatching);
  const totalPages = Math.ceil(totalMatching / pageSize);
  const currentPage = Math.floor(pageOffset / pageSize) + 1;

  return (
    <div className="space-y-6">
      {/* 1. Page Header with Claude-like Polish */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-1">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-teal-600 animate-pulse" />
            <p className="text-xs font-bold uppercase tracking-[.18em] text-teal-700">
              Investigation Workspace
            </p>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 mt-1">
            Safety Incidents
          </h2>
          <p className="text-sm text-slate-500 mt-1.5 max-w-2xl leading-relaxed">
            Investigate observations, review PPE findings, and manage assessments.
          </p>
        </div>

        {/* Quick Actions */}
        <div className="flex flex-wrap items-center gap-2.5">
          {onNavigate ? (
            <button
              type="button"
              onClick={() => onNavigate('analysis')}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs sm:text-sm font-semibold transition-colors shadow-xs"
            >
              <Sparkles size={16} />
              <span>Analyze Another Image</span>
            </button>
          ) : (
            <a
              href="#analysis"
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-teal-700 hover:bg-teal-800 text-white text-xs sm:text-sm font-semibold transition-colors shadow-xs"
            >
              <Sparkles size={16} />
              <span>Analyze Another Image</span>
            </a>
          )}

          <button
            type="button"
            onClick={() => {
              void executeQuery();
              parentOnRefresh?.();
            }}
            disabled={isLoading}
            className="inline-flex items-center gap-2 px-3.5 py-2.5 rounded-xl bg-white border border-slate-200 hover:border-slate-300 text-slate-700 text-xs sm:text-sm font-semibold transition-colors shadow-2xs disabled:opacity-50"
            title={`Last refreshed at ${lastRefreshed.toLocaleTimeString()}`}
          >
            <RefreshCw size={15} className={isLoading ? 'animate-spin text-teal-700' : 'text-slate-500'} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. Meaningful Backend Summary Metrics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Metric 1: Total Observations */}
        <div className="p-4 sm:p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Total Observations
            </span>
            <div className="w-8 h-8 rounded-xl bg-teal-50 text-teal-700 flex items-center justify-center">
              <History size={16} />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
              {totalObservations}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">Recorded audit trail</p>
          </div>
        </div>

        {/* Metric 2: Pending Assessments (High Priority) */}
        <div
          className={`p-4 sm:p-5 rounded-2xl bg-white border shadow-2xs flex flex-col justify-between transition-colors ${
            pendingAssessments > 0 ? 'border-amber-300 ring-2 ring-amber-400/20 bg-amber-50/20' : 'border-slate-200'
          }`}
        >
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-900">
              Pending Assessments
            </span>
            <div className="w-8 h-8 rounded-xl bg-amber-100 text-amber-800 flex items-center justify-center">
              <Clock size={16} />
            </div>
          </div>
          <div className="mt-3">
            <div className="flex items-baseline gap-2">
              <p className="text-2xl sm:text-3xl font-bold tracking-tight text-amber-950">
                {pendingAssessments}
              </p>
              {pendingAssessments > 0 && (
                <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-200 text-amber-900">
                  Needs Context
                </span>
              )}
            </div>
            <p className="text-[11px] text-amber-800/80 mt-1">Awaiting operator scoring input</p>
          </div>
        </div>

        {/* Metric 3: High / Critical Findings */}
        <div className="p-4 sm:p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider text-rose-800">
              High / Critical
            </span>
            <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-700 flex items-center justify-center">
              <ShieldAlert size={16} />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-2xl sm:text-3xl font-bold tracking-tight text-rose-900">
              {highCriticalFindings}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">Urgent & actionable findings</p>
          </div>
        </div>

        {/* Metric 4: Completed Assessments */}
        <div className="p-4 sm:p-5 rounded-2xl bg-white border border-slate-200 shadow-2xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-800">
              Completed Assessments
            </span>
            <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center">
              <CheckCircle2 size={16} />
            </div>
          </div>
          <div className="mt-3">
            <p className="text-2xl sm:text-3xl font-bold tracking-tight text-emerald-950">
              {completedAssessments}
            </p>
            <p className="text-[11px] text-slate-400 mt-1">Fully calculated risk records</p>
          </div>
        </div>
      </div>

      {/* Direct link feedback or error banner */}
      {(directLinkObs || directLinkError) && (
        <button type="button" onClick={returnToHistory} className="text-sm font-semibold text-teal-800 underline">Return to observation history</button>
      )}
      {supplemental && (
        <section aria-label="Linked observation outside current page" className="space-y-3">
          <p className="text-xs text-slate-600">Linked observation — outside the paginated results below.</p>
          <ObservationRow observation={directLinkObs} isExpanded={expandedId === directLinkObs.observation_id}
            onToggleExpand={() => toggleExpand(directLinkObs.observation_id)} highlightedAssessmentId={targetAssessmentId}
            onAssessmentUpdated={handleAssessmentUpdated} onWorkAreaUpdated={handleWorkAreaUpdated} />
        </section>
      )}
      {directLinkError && (
        <div role="alert" className="p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-xs text-rose-800 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2">
            <AlertCircle size={16} className="text-rose-600 shrink-0 mt-0.5" />
            <span>{directLinkError}</span>
          </div>
          <button
            type="button"
            onClick={() => setDirectLinkError(null)}
            className="text-rose-600 hover:text-rose-900 font-bold"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 3. Risk & Assessment Filter Tabs */}
      <div className="bg-white rounded-2xl border border-slate-200 p-2 shadow-2xs">
        <p className="px-2 pb-1 text-[10px] text-slate-500">Risk tabs match individual findings; each card shows the observation’s highest confirmed risk.</p>
        <div className="flex flex-wrap items-center gap-1.5 sm:gap-2">
          {RISK_TABS.map((tab) => {
            const isSelected = selectedRisk === tab.id;
            let count: number | undefined;

            if (tab.id === 'All') {
              count = queryResult?.unfiltered_risk_total;
            } else if (queryResult?.observation_counts) {
              count = queryResult.observation_counts[tab.id];
            }

            const isPendingTab = tab.id === 'Pending';

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setSelectedRisk(tab.id);
                  setPageOffset(0);
                }}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all select-none ${
                  isSelected
                    ? isPendingTab
                      ? 'bg-amber-500 text-slate-950 shadow-xs'
                      : 'bg-teal-800 text-white shadow-xs'
                    : isPendingTab && (count ?? 0) > 0
                    ? 'bg-amber-50 text-amber-900 hover:bg-amber-100/80 border border-amber-200'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                {isPendingTab && <Clock size={13} className={isSelected ? 'text-slate-950' : 'text-amber-700'} />}
                <span>{tab.label}</span>
                {count !== undefined && (
                  <span
                    className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${
                      isSelected
                        ? isPendingTab
                          ? 'bg-slate-950/20 text-slate-950'
                          : 'bg-white/20 text-white'
                        : isPendingTab
                        ? 'bg-amber-200 text-amber-950'
                        : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* 4. Search & Additional Filters Toolbar */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Search by Observation ID */}
          <div className="lg:col-span-2">
            <label htmlFor={searchInputId} className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Search by Observation ID
            </label>
            <div className="relative">
              <Search size={15} className="absolute left-3 top-2.5 text-slate-400" />
              <input
                id={searchInputId}
                type="text"
                value={searchId}
                onChange={(e) => {
                  setSearchId(e.target.value);
                  setPageOffset(0);
                }}
                placeholder="e.g. obs-9a2c8..."
                className="w-full pl-9 pr-8 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors"
              />
              {searchId && (
                <button
                  type="button"
                  onClick={() => setSearchId('')}
                  className="absolute right-2.5 top-2.5 text-slate-400 hover:text-slate-600"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>

          {/* Work Area / Zone filter */}
          <div>
            <label htmlFor={workAreaSelectId} className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Work Area / Zone
            </label>
            <div className="relative">
              <MapPin size={15} className="absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
              <select
                id={workAreaSelectId}
                value={selectedArea}
                onChange={(e) => {
                  setSelectedArea(e.target.value);
                  setPageOffset(0);
                }}
                className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors"
              >
                <option value="">All Work Areas</option>
                {workAreas.map((area) => (
                  <option key={area} value={area}>
                    {area}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Date range: Start Date */}
          <div>
            <label htmlFor={startDateInputId} className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              Start Date
            </label>
            <div className="relative">
              <Calendar size={15} className="absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
              <input
                id={startDateInputId}
                type="date"
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value);
                  setPageOffset(0);
                }}
                className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors"
              />
            </div>
          </div>

          {/* Date range: End Date */}
          <div>
            <label htmlFor={endDateInputId} className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
              End Date
            </label>
            <div className="relative">
              <Calendar size={15} className="absolute left-3 top-2.5 text-slate-400 pointer-events-none" />
              <input
                id={endDateInputId}
                type="date"
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value);
                  setPageOffset(0);
                }}
                className="w-full pl-9 pr-3 py-2 text-xs sm:text-sm bg-slate-50 border border-slate-200 rounded-xl focus:bg-white focus:outline-hidden focus:ring-2 focus:ring-teal-500 focus:border-teal-500 transition-colors"
              />
            </div>
          </div>
        </div>

        {/* Toolbar Footer: Sort & Clear Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">Sort:</span>
            <div className="inline-flex items-center gap-1">
              <ArrowUpDown size={13} className="text-slate-400" />
              <label htmlFor={sortSelectId} className="sr-only">Sort observations</label>
              <select
                id={sortSelectId}
                value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value as 'newest' | 'oldest')}
                className="bg-transparent font-semibold text-slate-700 hover:text-slate-900 focus:outline-hidden"
              >
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
              </select>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex items-center gap-1.5 font-semibold text-teal-700 hover:text-teal-900 transition-colors"
              >
                <X size={13} />
                <span>Clear Filters</span>
              </button>
            )}
            <span className="text-slate-400">
              Showing {currentStart}–{currentEnd} of {totalMatching} matched observations
            </span>
          </div>
        </div>
      </div>

      {/* 5. Main Results View States */}
      {/* State 1: Database Unconfigured (503) */}
      {!isDbConfigured && !isLoading && (
        <div className="p-8 rounded-2xl bg-white border border-slate-200 shadow-2xs text-center">
          <Database size={32} className="text-slate-300 mx-auto mb-2" />
          <h4 className="font-bold text-slate-800 text-sm">Database Unconfigured or Unavailable</h4>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Persistent observation history requires an active PostgreSQL connection. Check your database configuration and refresh.
          </p>
          <button
            type="button"
            onClick={() => void executeQuery()}
            className="mt-4 px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs font-semibold transition-colors"
          >
            Retry Connection
          </button>
        </div>
      )}

      {/* State 2: Error State */}
      {isDbConfigured && errorMessage && !isLoading && (
        <div className="p-5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 flex items-start justify-between gap-3">
          <div className="flex items-start gap-2.5">
            <AlertTriangle size={18} className="text-rose-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="font-bold text-rose-900 text-sm">Failed to Query Safety Incidents</h4>
              <p className="text-xs text-rose-700 mt-0.5">{errorMessage}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => void executeQuery()}
            className="px-3.5 py-1.5 bg-rose-100 hover:bg-rose-200 text-rose-900 rounded-lg text-xs font-semibold shrink-0 transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* State 3: Loading Skeleton */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((idx) => (
            <div
              key={idx}
              className="p-5 rounded-2xl border border-slate-200 bg-white shadow-2xs animate-pulse flex items-center justify-between"
            >
              <div className="flex items-center gap-3.5">
                <div className="w-16 h-16 rounded-xl bg-slate-200" />
                <div className="space-y-2">
                  <div className="h-4 w-44 bg-slate-200 rounded" />
                  <div className="h-3 w-64 bg-slate-200 rounded" />
                </div>
              </div>
              <div className="h-7 w-24 bg-slate-200 rounded-full" />
            </div>
          ))}
        </div>
      )}

      {/* State 4: Empty State */}
      {isDbConfigured && !isLoading && !errorMessage && displayItems.length === 0 && (
        <div className="p-12 text-center rounded-2xl border border-dashed border-slate-300 bg-white shadow-2xs">
          <Filter size={32} className="text-slate-300 mx-auto mb-2" />
          <h3 className="font-bold text-slate-800 text-base">No Matching Safety Incidents</h3>
          <p className="text-xs text-slate-500 mt-1.5 max-w-md mx-auto leading-relaxed">
            {hasActiveFilters
              ? 'No observations match your current filter criteria. Try adjusting your risk filter, search query, or date range.'
              : 'No safety observations have been recorded yet. Submit an image assessment in AI Safety Analysis to begin.'}
          </p>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="mt-4 px-4 py-2 bg-teal-700 hover:bg-teal-800 text-white rounded-xl text-xs font-semibold transition-colors"
            >
              Reset All Filters
            </button>
          )}
        </div>
      )}

      {/* State 5: Observations List with Redesigned Rows */}
      {isDbConfigured && !isLoading && !errorMessage && displayItems.length > 0 && (
        <div className="space-y-3" aria-label="Paginated observations">
          {displayItems.map((obs) => (
            <ObservationRow
              key={obs.observation_id}
              observation={obs}
              isExpanded={expandedId === obs.observation_id}
              onToggleExpand={() => toggleExpand(obs.observation_id)}
              highlightedAssessmentId={expandedId === obs.observation_id ? targetAssessmentId : null}
              onAssessmentUpdated={handleAssessmentUpdated}
              onWorkAreaUpdated={handleWorkAreaUpdated}
            />
          ))}
        </div>
      )}

      {/* 6. Real Pagination Controls */}
      {isDbConfigured && !isLoading && totalMatching > 0 && (
        <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-2xs flex flex-wrap items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-slate-500 font-medium">Rows per page:</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPageOffset(0);
              }}
              className="bg-slate-50 border border-slate-200 rounded-lg px-2 py-1 font-semibold text-slate-700 focus:outline-hidden"
            >
              <option value={10}>10</option>
              <option value={20}>20</option>
              <option value={50}>50</option>
            </select>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-slate-500">
              Page <strong className="text-slate-800">{currentPage}</strong> of{' '}
              <strong className="text-slate-800">{Math.max(1, totalPages)}</strong>
            </span>

            <div className="inline-flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => setPageOffset((prev) => Math.max(0, prev - pageSize))}
                disabled={pageOffset === 0}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 hover:bg-slate-100 text-slate-700 font-semibold rounded-lg disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <button
                type="button"
                onClick={() => setPageOffset((prev) => prev + pageSize)}
                disabled={pageOffset + pageSize >= totalMatching}
                className="px-3 py-1.5 bg-slate-50 border border-slate-200 hover:bg-slate-100 text-slate-700 font-semibold rounded-lg disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
