import React from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  Clock,
  Sparkles,
  CheckCircle2,
} from 'lucide-react';
import type { AssessmentsResponse } from '../types';
import {
  formatHazardType,
  formatRiskBand,
  formatConfidence,
} from '../utils/formatters';

interface AssessmentResultsProps {
  assessment: AssessmentsResponse;
}

export const AssessmentResults: React.FC<AssessmentResultsProps> = ({ assessment }) => {
  const { observation_id, detected_hazards, assessments, pending_hazards } = assessment;
  const hasViolations = detected_hazards.length > 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden mb-8">
      {/* Header bar */}
      <div className="p-6 bg-slate-900 text-white flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div
            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              hasViolations
                ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {hasViolations ? <ShieldAlert className="w-5 h-5" /> : <ShieldCheck className="w-5 h-5" />}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-base font-bold text-white">Assessment Results</h2>
              <span className="text-xs bg-slate-800 text-slate-300 font-mono px-2.5 py-0.5 rounded border border-slate-700">
                {observation_id}
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Site Risk Agent inference and educational rule-based scoring
            </p>
          </div>
        </div>

        {/* Counter Pills */}
        <div className="flex items-center space-x-2">
          <span className="text-xs px-2.5 py-1 rounded-md bg-slate-800 border border-slate-700 text-slate-300">
            Detected: <strong className="text-white">{detected_hazards.length}</strong>
          </span>
          <span className="text-xs px-2.5 py-1 rounded-md bg-emerald-950/60 border border-emerald-700/50 text-emerald-300">
            Completed: <strong className="text-white">{assessments.length}</strong>
          </span>
          {pending_hazards.length > 0 && (
            <span className="text-xs px-2.5 py-1 rounded-md bg-amber-950/60 border border-amber-700/50 text-amber-300">
              Pending: <strong className="text-white">{pending_hazards.length}</strong>
            </span>
          )}
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Zero Hazards Found State */}
        {!hasViolations && (
          <div className="p-6 rounded-xl bg-emerald-50/60 border border-emerald-200 text-center flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mb-3">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-emerald-900 mb-1">
              Compliant Site Conditions
            </h3>
            <p className="text-sm text-emerald-700 max-w-md">
              No PPE violations or supported hazards were detected in the inspected image. All
              compliant workers and equipment have been filtered.
            </p>
          </div>
        )}

        {/* Completed Risk Assessments */}
        {assessments.length > 0 && (
          <div>
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-4 flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-amber-600" />
              <span>Completed Hazard Assessments ({assessments.length})</span>
            </h3>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {assessments.map((ass, idx) => {
                const bandStyle = formatRiskBand(ass.risk_band);
                return (
                  <div
                    key={`${ass.hazard_type}-${idx}`}
                    className="p-5 rounded-xl border border-slate-200 bg-white shadow-xs hover:border-slate-300 transition-all flex flex-col justify-between"
                  >
                    <div>
                      {/* Top Bar: Hazard Title & Risk Band Badge */}
                      <div className="flex items-start justify-between gap-3 mb-3">
                        <div>
                          <h4 className="font-semibold text-slate-900 text-base">
                            {formatHazardType(ass.hazard_type)}
                          </h4>
                          <span className="text-xs font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                            source: {ass.source_label}
                          </span>
                        </div>
                        <span
                          className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border ${bandStyle.badgeClass}`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full mr-1.5 ${bandStyle.dotClass}`}
                          />
                          {bandStyle.label} ({ass.risk_score})
                        </span>
                      </div>

                      {/* Formula Badges (S x L x E) */}
                      <div className="grid grid-cols-3 gap-2 my-3 p-2.5 rounded-lg bg-slate-50 border border-slate-100 text-center">
                        <div>
                          <div className="text-xs text-slate-500 uppercase font-semibold">
                            Severity
                          </div>
                          <div className="text-sm font-bold text-slate-800">{ass.severity} / 5</div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 uppercase font-semibold">
                            Likelihood
                          </div>
                          <div className="text-sm font-bold text-slate-800">
                            {ass.likelihood} / 5
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-slate-500 uppercase font-semibold">
                            Exposure
                          </div>
                          <div className="text-sm font-bold text-slate-800">{ass.exposure} / 4</div>
                        </div>
                      </div>

                      {/* Agent Reasoning Explanation */}
                      <p className="text-xs text-slate-600 leading-relaxed mb-3">
                        {ass.explanation}
                      </p>
                    </div>

                    {/* Bottom Metadata: Confidence & Formula */}
                    <div className="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                      <span>
                        Detection Confidence:{' '}
                        <strong className="text-slate-700">
                          {formatConfidence(ass.detection_confidence)}
                        </strong>
                      </span>
                      <span className="font-mono text-[11px] bg-slate-100 px-2 py-0.5 rounded text-slate-500">
                        {ass.severity} × {ass.likelihood} × {ass.exposure} = {ass.risk_score}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Pending Hazards Section */}
        {pending_hazards.length > 0 && (
          <div className="p-5 rounded-xl bg-amber-50/70 border border-amber-200">
            <div className="flex items-start space-x-3 mb-3">
              <Clock className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="text-sm font-bold text-amber-900">
                  Pending Assessments ({pending_hazards.length})
                </h4>
                <p className="text-xs text-amber-700 mt-0.5">
                  Hazards were identified by visual detection, but risk scoring requires operational
                  exposure duration and repetitions.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-3">
              {pending_hazards.map((hazard, idx) => (
                <div
                  key={`${hazard.hazard_type}-pending-${idx}`}
                  className="bg-white p-3.5 rounded-lg border border-amber-200 text-xs flex items-center justify-between shadow-xs"
                >
                  <div>
                    <span className="font-semibold text-slate-800 block">
                      {formatHazardType(hazard.hazard_type)}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      label: {hazard.source_label}
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="inline-block px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800">
                      Pending Inputs
                    </span>
                    <span className="block text-[11px] text-slate-400 mt-0.5">
                      Conf: {formatConfidence(hazard.detection_confidence)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
