import React, { useEffect, useState } from 'react';
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
import type { AssessmentCompletionResponse, ObservationDetailResponse, PersistedAssessmentResponse, SafetyDecisionResponse } from '../types';
import { useAuth } from '../auth/AuthContext';
import { PendingAssessmentCompletion } from './PendingAssessmentCompletion';
import { SafetyDecisionPanel } from './SafetyDecisionPanel';
import {
  formatHazardType,
  formatRiskBand,
  formatConfidence,
  formatDateTime,
} from '../utils/formatters';
import { fetchObservationImage, updateObservationWorkArea } from '../api/client';

interface ObservationHistoryProps {
  observations: ObservationDetailResponse[];
  isLoading: boolean;
  isDatabaseConfigured: boolean;
  error: string | null;
  onRefresh: () => void;
  onAssessmentCompleted: (observationId: string) => void;
  onWorkAreaUpdated: (observation: ObservationDetailResponse) => void;
}

// Older observations may have no stored decision snapshot. Validate metadata before rendering it.
const storedDecision = (metadata: Record<string, unknown> | null | undefined): SafetyDecisionResponse | null => {
  const value = metadata?.safety_decision;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const decision = value as Record<string, unknown>;
  if (!['alert', 'warning', 'pending', 'no_alert'].includes(String(decision.outcome)) ||
      typeof decision.reason !== 'string' ||
      typeof decision.priority !== 'string' ||
      typeof decision.policy_version !== 'string' ||
      !Array.isArray(decision.supporting_evidence) ||
      (decision.risk_band !== null && typeof decision.risk_band !== 'string')) return null;
  const validEvidence = decision.supporting_evidence.every((item: unknown) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return false;
    const evidence = item as Record<string, unknown>;
    return typeof evidence.hazard_type === 'string' &&
      typeof evidence.source_label === 'string' &&
      (evidence.detection_confidence == null || typeof evidence.detection_confidence === 'number') &&
      (evidence.risk_score == null || typeof evidence.risk_score === 'number') &&
      (evidence.risk_band == null || typeof evidence.risk_band === 'string');
  });
  return validEvidence ? value as SafetyDecisionResponse : null;
};

const latestAssessment = (assessments: PersistedAssessmentResponse[]): PersistedAssessmentResponse | undefined =>
  assessments.reduce<PersistedAssessmentResponse | undefined>(
    (latest, item) => !latest || item.assessment_version > latest.assessment_version ? item : latest,
    undefined,
  );

const ObservationImages: React.FC<{ observationId: string }> = ({ observationId }) => {
  const [images, setImages] = useState<{ original?: string; annotated?: string }>({});

  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    const load = async (variant: 'original' | 'annotated') => {
      try {
        const url = await fetchObservationImage(observationId, variant);
        urls.push(url);
        if (active) setImages((current) => ({ ...current, [variant]: url }));
        else URL.revokeObjectURL(url);
      } catch {
        // Missing image variants are expected for older persisted records.
      }
    };
    void load('original'); void load('annotated');
    return () => { active = false; urls.forEach((url) => URL.revokeObjectURL(url)); };
  }, [observationId]);

  return (
    <div>
      <h5 className="font-bold text-slate-700 mb-2 uppercase tracking-wider text-[11px]">
        Observation Images
      </h5>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {images.original && (
          <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
            <div className="px-3 py-2 text-xs font-semibold text-slate-600">Original upload</div>
            <img
              src={images.original}
              alt={`Original image for observation ${observationId}`}
              className="w-full h-auto object-contain bg-slate-900"
            />
          </div>
        )}
        {images.annotated && (
          <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
            <div className="px-3 py-2 text-xs font-semibold text-slate-600">
              Detection overlay
            </div>
            <img
              src={images.annotated}
              alt={`Annotated image for observation ${observationId}`}
              className="w-full h-auto object-contain bg-slate-900"
            />
          </div>
        )}
      </div>
      {!images.original && !images.annotated && (
        <p className="text-slate-400 italic">Image unavailable for this observation.</p>
      )}
    </div>
  );
};

export const ObservationHistory: React.FC<ObservationHistoryProps> = ({
  observations,
  isLoading,
  isDatabaseConfigured,
  error,
  onRefresh,
  onAssessmentCompleted,
  onWorkAreaUpdated,
}) => {
  const { user } = useAuth();
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [lastCompletion, setLastCompletion] = useState<AssessmentCompletionResponse | null>(null);
  const [editingAreaId, setEditingAreaId] = useState<string | null>(null);
  const [areaDraft, setAreaDraft] = useState('');
  const [areaError, setAreaError] = useState<string | null>(null);
  const [areaSavedId, setAreaSavedId] = useState<string | null>(null);
  const [areaSaving, setAreaSaving] = useState(false);
  const canComplete = user?.role === 'safety_officer' || user?.role === 'admin';

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  const saveArea = async (observationId: string) => {
    if (!areaDraft.trim()) { setAreaError('Enter a named work area.'); return; }
    setAreaSaving(true); setAreaError(null);
    try {
      const updated = await updateObservationWorkArea(observationId, areaDraft.trim());
      onWorkAreaUpdated(updated);
      setEditingAreaId(null);
      setAreaSavedId(observationId);
    } catch (reason) {
      setAreaError(reason instanceof Error ? reason.message : 'Unable to update work area');
    } finally { setAreaSaving(false); }
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
        {!isDatabaseConfigured && !isLoading && (
          <div className="p-5 rounded-xl bg-slate-50 border border-slate-200 flex items-start space-x-3 text-slate-600">
            <Database className="w-5 h-5 text-slate-400 shrink-0 mt-0.5" />
            <div className="text-sm">
              <h4 className="font-semibold text-slate-800">Observation history unavailable</h4>
              <p className="text-slate-500 mt-1">Saved records cannot be loaded right now. Check the backend and database connection, then refresh.</p>
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
              No observations have been recorded yet. Open AI Safety Analysis to submit an image.
            </p>
          </div>
        )}

        {/* State 5: Observations List */}
        {isDatabaseConfigured && !isLoading && !error && observations.length > 0 && (
          <div className="space-y-3">
            {observations.map((obs) => {
              const isExpanded = expandedId === obs.observation_id;
              const namedArea = obs.work_area?.trim() && !['unknown', 'unspecified', 'unassigned work area'].includes(obs.work_area.trim().toLowerCase()) ? obs.work_area.trim() : null;
              const decision = storedDecision(obs.raw_metadata);
              const hazardCount = obs.detected_hazards.length;
              const allAssessments = obs.detected_hazards.map((h) => latestAssessment(h.assessments));
              const hasHighOrCritical = allAssessments.some(
                (a) => a?.risk_band === 'High' || a?.risk_band === 'Critical'
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
                            <span>{namedArea || 'Unassigned work area'}</span>
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
                      <div className="rounded-lg border border-slate-200 bg-white p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800">Work Area / Zone: {namedArea || 'Unassigned work area'}</p>
                          {canComplete && editingAreaId !== obs.observation_id && <button type="button" onClick={() => { setEditingAreaId(obs.observation_id); setAreaDraft(namedArea || ''); setAreaError(null); setAreaSavedId(null); }} className="text-sm font-semibold text-teal-700 underline">{namedArea ? 'Edit' : 'Assign work area'}</button>}
                        </div>
                        {areaSavedId === obs.observation_id && <p role="status" className="mt-2 text-teal-700">Work area saved. Analytics and reports will reflect this assignment on refresh.</p>}
                        {editingAreaId === obs.observation_id && <form onSubmit={(event) => { event.preventDefault(); void saveArea(obs.observation_id); }} className="mt-3 flex flex-wrap items-end gap-2">
                          <label className="text-xs font-semibold text-slate-700">Named work area
                            <input autoFocus type="text" maxLength={255} value={areaDraft} onChange={(event) => setAreaDraft(event.target.value)} placeholder="e.g. Zone A" className="mt-1 block rounded-lg border border-slate-300 px-3 py-2 text-sm" />
                          </label>
                          <button type="submit" disabled={areaSaving || !areaDraft.trim()} className="rounded-lg bg-teal-700 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{areaSaving ? 'Saving…' : 'Save'}</button>
                          <button type="button" onClick={() => { setEditingAreaId(null); setAreaError(null); }} className="rounded-lg border border-slate-300 px-3 py-2 text-sm">Cancel</button>
                          {areaError && <p role="alert" className="w-full text-rose-700">{areaError}</p>}
                        </form>}
                      </div>
                      {/* Observation Metadata Grid */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-3 bg-white rounded-lg border border-slate-200">
                        <div>
                          <span className="text-slate-400 block">Source</span>
                          <span className="font-medium text-slate-800 truncate block">
                            {obs.source === 'image_upload:site_image' ? 'Uploaded image' : obs.source}
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
                          <span className="text-slate-400 block">Scoring repetition input</span>
                          <span className="font-medium text-slate-800">
                            {obs.repeated_count ?? '—'}
                          </span>
                        </div>
                      </div>

                      {decision ? (
                        <SafetyDecisionPanel decision={decision} compact />
                      ) : (
                        <p className="text-slate-500">Decision snapshot unavailable for this historical observation.</p>
                      )}

                      {lastCompletion?.observation_id === obs.observation_id && (
                        <div className="p-3 rounded-lg border border-teal-200 bg-teal-50 text-teal-900">
                          <p className="font-semibold">Assessment #{lastCompletion.assessment_id} completed</p>
                          <p className="mt-1">Risk: {lastCompletion.assessment.severity} × {lastCompletion.assessment.likelihood} × {lastCompletion.assessment.exposure} = {lastCompletion.assessment.risk_score} ({lastCompletion.assessment.risk_band}).</p>
                          {lastCompletion.alert_ids.length > 0 && <p className="mt-1">Actionable alert{lastCompletion.alert_ids.length > 1 ? 's' : ''} #{lastCompletion.alert_ids.join(', #')} linked to this observation.</p>}
                          {lastCompletion.safety_decision.outcome === 'pending' && <p className="mt-1">Other findings in this observation still need assessment.</p>}
                        </div>
                      )}

                      <ObservationImages observationId={obs.observation_id} />

                      {/* Detected Hazards in this observation */}
                      <div>
                        <h5 className="font-bold text-slate-700 mb-2 uppercase tracking-wider text-[11px]">
                          Detected Hazards & Assessments ({obs.detected_hazards.length})
                        </h5>

                        {obs.detected_hazards.length === 0 ? (
                          <p className="text-slate-500 italic">No supported PPE findings recorded. This does not confirm site safety.</p>
                        ) : (
                          <div className="space-y-2">
                            {obs.detected_hazards.map((hazard, hIdx) => {
                              const ass = latestAssessment(hazard.assessments);
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
                                      Detection confidence: {formatConfidence(hazard.detection_confidence)}
                                    </span>
                                  </div>

                                  <div>
                                    {ass?.status === 'completed' ? (
                                      <div className="text-right">
                                        <span className={`px-2 py-0.5 rounded-full font-bold text-[11px] border ${bandStyle.badgeClass}`}>
                                          {bandStyle.label} ({ass.risk_score})
                                        </span>
                                        <p className="text-slate-500 mt-1">{ass.severity} × {ass.likelihood} × {ass.exposure} = {ass.risk_score}</p>
                                      </div>
                                    ) : (
                                      <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800">
                                        Pending inputs
                                      </span>
                                    )}
                                  </div>
                                  {ass?.status === 'pending' && canComplete && (
                                    <PendingAssessmentCompletion
                                      observation={obs}
                                      assessment={ass}
                                      onCompleted={(result) => {
                                        setLastCompletion(result);
                                        onAssessmentCompleted(result.observation_id);
                                      }}
                                    />
                                  )}
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
