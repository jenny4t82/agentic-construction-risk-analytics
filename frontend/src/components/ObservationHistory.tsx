import React, { useState } from 'react';
import {
  History,
  RotateCw,
  Database,
  Calendar,
  MapPin,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import type { ObservationDetailResponse } from '../types';
import {
  formatHazardType,
  formatRiskBand,
  formatConfidence,
  formatDateTime,
} from '../utils/formatters';

interface ObservationHistoryProps {
  observations: ObservationDetailResponse[];
  isLoading: boolean;
  isDatabaseConfigured: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const ObservationHistory: React.FC<ObservationHistoryProps> = ({
  observations,
  isLoading,
  isDatabaseConfigured,
  error,
  onRefresh,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden mb-8">
      {/* Header */}
      <div className="p-6 border-b border-slate-100 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900 flex items-center space-x-2">
            <History className="w-5 h-5 text-slate-700" />
            <span>Site Observation History</span>
          </h2>
          <p className="text-sm text-slate-500">
            Persistent audit trail of site observations, detections, and risk calculations.
          </p>
        </div>

        <button
          type="button"
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center space-x-1.5 px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 disabled:opacity-50 transition-colors"
        >
          <RotateCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="p-6">
        {/* State 1: Database Unconfigured (503) */}
        {!isDatabaseConfigured && (
          <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 flex items-start space-x-3 text-slate-600">
            <Database className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
            <div className="text-sm">
              <h4 className="font-semibold text-slate-800">Database Persistence Unconfigured</h4>
              <p className="text-slate-500 mt-1">
                The platform is running in stateless mode because{' '}
                <code className="text-xs bg-slate-200/80 px-1.5 py-0.5 rounded text-slate-700">
                  DATABASE_URL
                </code>{' '}
                is not set in the environment. Image assessments and risk scoring function normally,
                but monitoring records are not saved to PostgreSQL.
              </p>
            </div>
          </div>
        )}

        {/* State 2: Error State */}
        {isDatabaseConfigured && error && (
          <div className="p-5 rounded-xl bg-red-50 border border-red-200 text-red-700 flex items-start justify-between">
            <div className="flex items-start space-x-3">
              <AlertTriangle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-semibold text-red-800">Failed to Retrieve History</h4>
                <p className="text-sm text-red-600 mt-0.5">{error}</p>
              </div>
            </div>
            <button
              onClick={onRefresh}
              className="text-xs font-semibold px-3 py-1 bg-red-100 hover:bg-red-200 text-red-800 rounded transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* State 3: Loading Skeleton */}
        {isDatabaseConfigured && isLoading && (
          <div className="space-y-3">
            {[1, 2, 3].map((n) => (
              <div
                key={n}
                className="p-4 rounded-xl border border-slate-100 bg-slate-50 animate-pulse flex items-center justify-between"
              >
                <div className="space-y-2">
                  <div className="h-4 w-48 bg-slate-200 rounded" />
                  <div className="h-3 w-32 bg-slate-200 rounded" />
                </div>
                <div className="h-6 w-20 bg-slate-200 rounded-full" />
              </div>
            ))}
          </div>
        )}

        {/* State 4: Empty State */}
        {isDatabaseConfigured && !isLoading && !error && observations.length === 0 && (
          <div className="p-8 text-center rounded-xl border border-dashed border-slate-200">
            <History className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <h3 className="font-semibold text-slate-700 text-sm">No Recorded Observations</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              No monitoring records found in the database. Upload an image above to record the first
              site observation.
            </p>
          </div>
        )}

        {/* State 5: Observations List */}
        {isDatabaseConfigured && !isLoading && !error && observations.length > 0 && (
          <div className="space-y-3">
            {observations.map((obs) => {
              const isExpanded = expandedId === obs.observation_id;
              const hazardCount = obs.detected_hazards.length;
              const allAssessments = obs.detected_hazards.flatMap((h) => h.assessments);
              const hasHighOrCritical = allAssessments.some(
                (a) => a.risk_band === 'High' || a.risk_band === 'Critical'
              );

              return (
                <div
                  key={obs.observation_id}
                  className="rounded-xl border border-slate-200 bg-white hover:border-slate-300 transition-all overflow-hidden"
                >
                  {/* Summary Row */}
                  <div
                    onClick={() => toggleExpand(obs.observation_id)}
                    className="p-4 cursor-pointer flex flex-wrap items-center justify-between gap-3 select-none"
                  >
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 font-mono text-xs font-bold">
                        #{obs.observation_id.slice(-4)}
                      </div>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-slate-900 text-sm">
                            {obs.observation_id}
                          </span>
                          {hasHighOrCritical && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-100 text-red-700">
                              High Risk
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-3 text-xs text-slate-400 mt-0.5">
                          <span className="flex items-center space-x-1">
                            <Calendar className="w-3 h-3" />
                            <span>{formatDateTime(obs.observed_at)}</span>
                          </span>
                          <span className="flex items-center space-x-1">
                            <MapPin className="w-3 h-3" />
                            <span>{obs.work_area || 'unspecified'}</span>
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      {/* Hazards count badge */}
                      <span className="text-xs px-2.5 py-1 rounded-full font-medium bg-slate-100 text-slate-700">
                        {hazardCount} {hazardCount === 1 ? 'hazard' : 'hazards'}
                      </span>
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {/* Expandable Details Drawer */}
                  {isExpanded && (
                    <div className="p-4 bg-slate-50/60 border-t border-slate-100 text-xs space-y-4">
                      {/* Observation Metadata Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-white rounded-lg border border-slate-200">
                        <div>
                          <span className="text-slate-400 block">Source</span>
                          <span className="font-medium text-slate-800 truncate block">
                            {obs.source}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">People Count</span>
                          <span className="font-medium text-slate-800">
                            {obs.people_count ?? '—'}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Duration</span>
                          <span className="font-medium text-slate-800">
                            {obs.duration_minutes ? `${obs.duration_minutes} min` : '—'}
                          </span>
                        </div>
                        <div>
                          <span className="text-slate-400 block">Repetitions</span>
                          <span className="font-medium text-slate-800">
                            {obs.repeated_count ?? '—'}
                          </span>
                        </div>
                      </div>

                      {/* Detected Hazards in this observation */}
                      <div>
                        <h5 className="font-bold text-slate-700 mb-2 uppercase tracking-wider text-[11px]">
                          Detected Hazards & Assessments ({obs.detected_hazards.length})
                        </h5>

                        {obs.detected_hazards.length === 0 ? (
                          <p className="text-slate-400 italic">No hazards recorded.</p>
                        ) : (
                          <div className="space-y-2">
                            {obs.detected_hazards.map((hazard, hIdx) => {
                              const ass = hazard.assessments[0];
                              const bandStyle = formatRiskBand(ass?.risk_band);

                              return (
                                <div
                                  key={hazard.detected_hazard_id || hIdx}
                                  className="p-3 bg-white rounded-lg border border-slate-200 flex flex-wrap items-center justify-between gap-2"
                                >
                                  <div>
                                    <span className="font-semibold text-slate-800 block text-xs">
                                      {formatHazardType(hazard.hazard_type)}
                                    </span>
                                    <span className="text-[11px] text-slate-400 font-mono">
                                      label: {hazard.source_label} • conf:{' '}
                                      {formatConfidence(hazard.detection_confidence)}
                                    </span>
                                  </div>

                                  <div>
                                    {ass?.status === 'completed' ? (
                                      <span
                                        className={`px-2 py-0.5 rounded-full font-bold text-[11px] border ${bandStyle.badgeClass}`}
                                      >
                                        {bandStyle.label} ({ass.risk_score})
                                      </span>
                                    ) : (
                                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800">
                                        Pending inputs
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
