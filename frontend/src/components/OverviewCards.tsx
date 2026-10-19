import React from 'react';
import { Eye, AlertTriangle, Clock, TrendingUp } from 'lucide-react';
import type { ObservationDetailResponse, AssessmentsResponse } from '../types';

interface OverviewCardsProps {
  observations: ObservationDetailResponse[];
  latestAssessment: AssessmentsResponse | null;
  isDatabaseConfigured: boolean;
}

export const OverviewCards: React.FC<OverviewCardsProps> = ({
  observations,
  latestAssessment,
  isDatabaseConfigured,
}) => {
  // Aggregate statistics strictly from real API data
  let totalObservations = observations.length;
  let highOrCriticalRisks = 0;
  let totalPending = 0;
  const scores: number[] = [];

  if (isDatabaseConfigured && observations.length > 0) {
    for (const obs of observations) {
      for (const hazard of obs.detected_hazards) {
        for (const ass of hazard.assessments) {
          if (ass.status === 'completed' && ass.risk_score !== null && ass.risk_score !== undefined) {
            scores.push(ass.risk_score);
            if (ass.risk_band === 'High' || ass.risk_band === 'Critical') {
              highOrCriticalRisks += 1;
            }
          } else if (ass.status === 'pending') {
            totalPending += 1;
          }
        }
      }
    }
  } else if (latestAssessment) {
    // In stateless mode or when only latest assessment is available
    totalObservations = 1;
    for (const ass of latestAssessment.assessments) {
      scores.push(ass.risk_score);
      if (ass.risk_band === 'High' || ass.risk_band === 'Critical') {
        highOrCriticalRisks += 1;
      }
    }
    totalPending += latestAssessment.pending_hazards.length;
  }

  const avgScore =
    scores.length > 0 ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1) : '—';

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {/* Total Observations */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs hover:border-slate-300 transition-all">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-500">Site Observations</span>
          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
            <Eye className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-slate-900">{totalObservations}</span>
          <span className="text-xs text-slate-400">
            {isDatabaseConfigured ? 'saved in DB' : 'stateless session'}
          </span>
        </div>
      </div>

      {/* High & Critical Violations */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs hover:border-slate-300 transition-all">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-500">High / Critical Risks</span>
          <div className="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center">
            <AlertTriangle className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-red-600">{highOrCriticalRisks}</span>
          <span className="text-xs text-slate-400">band ≥ 40</span>
        </div>
      </div>

      {/* Pending Assessments */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs hover:border-slate-300 transition-all">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-500">Pending Scoring</span>
          <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
            <Clock className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-amber-600">{totalPending}</span>
          <span className="text-xs text-slate-400">needs duration/rep</span>
        </div>
      </div>

      {/* Average Risk Score */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs hover:border-slate-300 transition-all">
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-slate-500">Average Risk Score</span>
          <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
            <TrendingUp className="w-4 h-4" />
          </div>
        </div>
        <div className="flex items-baseline space-x-2">
          <span className="text-2xl font-bold text-slate-900">{avgScore}</span>
          <span className="text-xs text-slate-400">formula: S × L × E (1–100)</span>
        </div>
      </div>
    </div>
  );
};
