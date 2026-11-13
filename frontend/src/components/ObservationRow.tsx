import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  Calendar,
  Check,
  ChevronDown,
  ChevronRight,
  Clock,
  Copy,
  MapPin,
  Shield,
  ShieldAlert,
} from 'lucide-react';
import type {
  AssessmentCompletionResponse,
  ObservationDetailResponse,
  PersistedAssessmentResponse,
  RiskBand,
  SafetyDecisionResponse,
} from '../types';
import { useAuth } from '../auth/AuthContext';
import { ObservationThumbnail } from './ObservationThumbnail';
import { ObservationEvidenceViewer } from './ObservationEvidenceViewer';
import { PendingAssessmentCompletion } from './PendingAssessmentCompletion';
import { AssessmentContextEditor } from './AssessmentContextEditor';
import { SafetyDecisionPanel } from './SafetyDecisionPanel';
import {
  formatConfidence,
  formatDateTime,
  formatHazardType,
  formatRiskBand,
} from '../utils/formatters';
import { updateObservationWorkArea } from '../api/client';

interface Props {
  observation: ObservationDetailResponse;
  isExpanded: boolean;
  onToggleExpand: () => void;
  highlightedAssessmentId?: string | null;
  onAssessmentUpdated: (observationId: string) => void;
  onWorkAreaUpdated: (observation: ObservationDetailResponse) => void;
}

// Validate stored decision snapshot
const extractStoredDecision = (metadata: Record<string, unknown> | null | undefined): SafetyDecisionResponse | null => {
  const value = metadata?.safety_decision;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const decision = value as Record<string, unknown>;
  if (
    !['alert', 'warning', 'pending', 'no_alert'].includes(String(decision.outcome)) ||
    typeof decision.reason !== 'string' ||
    typeof decision.priority !== 'string' ||
    typeof decision.policy_version !== 'string' ||
    !Array.isArray(decision.supporting_evidence) ||
    (decision.risk_band !== null && typeof decision.risk_band !== 'string')
  ) {
    return null;
  }
  return value as SafetyDecisionResponse;
};

const getLatestAssessment = (assessments: PersistedAssessmentResponse[]): PersistedAssessmentResponse | undefined =>
  assessments.reduce<PersistedAssessmentResponse | undefined>(
    (latest, item) => (!latest || item.assessment_version > latest.assessment_version ? item : latest),
    undefined
  );

export function ObservationRow({
  observation,
  isExpanded,
  onToggleExpand,
  highlightedAssessmentId,
  onAssessmentUpdated,
  onWorkAreaUpdated,
}: Props) {
  const { user } = useAuth();
  const canManage = user?.role === 'safety_officer' || user?.role === 'admin';

  const [copied, setCopied] = useState(false);
  const [editingArea, setEditingArea] = useState(false);
  const [areaDraft, setAreaDraft] = useState('');
  const [areaSaving, setAreaSaving] = useState(false);
  const [areaError, setAreaError] = useState<string | null>(null);
  const [areaSuccess, setAreaSuccess] = useState(false);
  const [lastCompletion, setLastCompletion] = useState<AssessmentCompletionResponse | null>(null);
  const [confirmations, setConfirmations] = useState<Record<number, AssessmentCompletionResponse>>({});
  const rowRef = useRef<HTMLDivElement>(null);
  // Confirmed server responses remain visible while the parent refreshes persisted data.
  const obs = { ...observation, detected_hazards: observation.detected_hazards.map(h => ({
    ...h, assessments: h.assessments.map(a => a.assessment_id != null && a.status === 'pending' && confirmations[a.assessment_id]
      ? confirmations[a.assessment_id].assessment : a),
  })) };
  useEffect(() => {
    if (!lastCompletion) return;
    const next = rowRef.current?.querySelector<HTMLElement>('[data-pending-assessment] input, [data-pending-assessment] button[type="submit"]');
    next?.focus();
  }, [lastCompletion]);

  const namedArea =
    obs.work_area?.trim() && !['unknown', 'unspecified', 'unassigned work area'].includes(obs.work_area.trim().toLowerCase())
      ? obs.work_area.trim()
      : null;

  const decision = lastCompletion?.safety_decision ?? extractStoredDecision(obs.raw_metadata);
  const hazardCount = obs.detected_hazards.length;

  // Extract all current assessments
  const currentAssessments = obs.detected_hazards.map((h) => ({
    hazard: h,
    assessment: getLatestAssessment(h.assessments),
  }));

  const pendingAssessments = currentAssessments.filter(
    (item) => item.assessment?.status === 'pending' || item.assessment == null
  );
  const completedAssessments = currentAssessments.filter(
    (item) => item.assessment?.status === 'completed'
  );

  const pendingCount = pendingAssessments.length;

  // Distinct risk bands for summary row badges
  const distinctBands = Array.from(
    new Set(
      completedAssessments
        .map((item) => item.assessment?.risk_band)
        .filter((b): b is RiskBand => Boolean(b))
    )
  );

  const handleCopyId = (e: React.MouseEvent) => {
    e.stopPropagation();
    void navigator.clipboard.writeText(obs.observation_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const saveWorkArea = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!areaDraft.trim()) {
      setAreaError('Please enter a named work area.');
      return;
    }
    setAreaSaving(true);
    setAreaError(null);
    try {
      const updated = await updateObservationWorkArea(obs.observation_id, areaDraft.trim());
      onWorkAreaUpdated(updated);
      setEditingArea(false);
      setAreaSuccess(true);
      setTimeout(() => setAreaSuccess(false), 4000);
    } catch (err) {
      setAreaError(err instanceof Error ? err.message : 'Unable to update work area');
    } finally {
      setAreaSaving(false);
    }
  };

  return (
    <div
      ref={rowRef}
      className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
        isExpanded
          ? 'border-teal-300 bg-white shadow-md ring-1 ring-teal-500/20'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:shadow-xs'
      }`}
    >
      {/* Clickable Summary Row */}
      <div
        onClick={onToggleExpand}
        className="p-4 sm:p-5 cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 select-none"
        role="button"
        aria-expanded={isExpanded}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggleExpand();
          }
        }}
      >
        {/* Left: Thumbnail & Observation Identity */}
        <div className="flex items-start sm:items-center gap-3.5 min-w-0">
          <ObservationThumbnail observationId={obs.observation_id} size="md" />

          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-sm font-bold text-slate-900 tracking-tight">
                {obs.observation_id}
              </span>
              <button
                type="button"
                onClick={handleCopyId}
                title={copied ? 'Copied observation ID!' : 'Copy observation ID'}
                aria-label="Copy observation ID"
                className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
              >
                {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
              </button>

              {/* Work area badge */}
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
                <MapPin size={11} className="text-slate-400 shrink-0" />
                <span className="truncate max-w-[140px]">{namedArea || 'Unassigned work area'}</span>
              </span>

              {/* Date/Time badge */}
              <span className="inline-flex items-center gap-1 text-xs text-slate-400 whitespace-nowrap">
                <Calendar size={12} />
                <span>{formatDateTime(obs.observed_at)}</span>
              </span>
            </div>

            {/* Findings & Risk badges line */}
            <div className="flex flex-wrap items-center gap-1.5 mt-2">
              {/* Findings count badge */}
              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                {hazardCount} {hazardCount === 1 ? 'PPE Finding' : 'PPE Findings'}
              </span>

              {/* Visible Pending Count Badge (High Visibility) */}
              {pendingCount > 0 && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100 text-amber-900 border border-amber-300 ring-2 ring-amber-400/20 animate-pulse">
                  <AlertCircle size={12} className="text-amber-700" />
                  <span>
                    {pendingCount} Pending Context
                  </span>
                </span>
              )}

              {/* Risk Band Badges for Completed Assessments */}
              {distinctBands.map((band) => {
                const bandStyle = formatRiskBand(band);
                const countForBand = completedAssessments.filter(
                  (item) => item.assessment?.risk_band === band
                ).length;
                return (
                  <span
                    key={band}
                    className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold border ${bandStyle.badgeClass}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${bandStyle.dotClass}`} />
                    <span>{band}</span>
                    {countForBand > 1 && <span className="opacity-75">({countForBand})</span>}
                  </span>
                );
              })}

              {/* Zero-Hazard Neutral State */}
              {hazardCount === 0 && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                  <Shield size={11} className="text-slate-400" />
                  <span>No PPE Violations Detected (Neutral)</span>
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Overall Safety Decision snapshot & Expand control */}
        <div className="flex items-center justify-between md:justify-end gap-3 shrink-0 pt-2 md:pt-0 border-t md:border-t-0 border-slate-100">
          {pendingCount > 0 ? <span className="text-xs text-amber-800">Assessment in progress</span> : decision ? (
            <div className="text-left md:text-right">
              <span className="text-[10px] uppercase tracking-wider text-slate-400 block font-semibold">
                Overall Decision
              </span>
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-bold uppercase tracking-wider ${
                  decision.outcome === 'alert'
                    ? 'bg-rose-100 text-rose-800 border border-rose-200'
                    : decision.outcome === 'warning'
                    ? 'bg-amber-100 text-amber-800 border border-amber-200'
                    : decision.outcome === 'pending'
                    ? 'bg-amber-50 text-amber-900 border border-amber-200'
                    : 'bg-slate-100 text-slate-700 border border-slate-200'
                }`}
              >
                {decision.outcome}
              </span>
            </div>
          ) : (
            <span className="text-xs text-slate-400 italic">No decision snapshot</span>
          )}

          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
              isExpanded ? 'bg-teal-100 text-teal-800' : 'bg-slate-100 text-slate-400 hover:text-slate-600'
            }`}
          >
            {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          </div>
        </div>
      </div>

      {/* Expandable Inspection Details Drawer */}
      {isExpanded && (
        <div className="p-5 sm:p-6 bg-slate-50/70 border-t border-slate-100 space-y-6 text-slate-900">
          {/* Section 1: Two-column layout (Images on Left, Area/Context/Decision on Right) */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
            {/* Left: Images */}
            <div className="space-y-4">
              <ObservationEvidenceViewer observationId={obs.observation_id} />
            </div>

            {/* Right: Work Area, Metadata, and Overall Decision */}
            <div className="space-y-4">
              {/* Work Area Box */}
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <MapPin size={16} className="text-teal-700" />
                    <div>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                        Work Area / Zone
                      </span>
                      <p className="text-sm font-bold text-slate-900">
                        {namedArea || <span className="text-slate-400 italic font-normal">Unassigned work area</span>}
                      </p>
                    </div>
                  </div>

                  {canManage && !editingArea && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditingArea(true);
                        setAreaDraft(namedArea || '');
                        setAreaError(null);
                      }}
                      className="text-xs font-semibold text-teal-700 hover:text-teal-900 underline"
                    >
                      {namedArea ? 'Change Work Area' : 'Assign Work Area'}
                    </button>
                  )}
                </div>

                {areaSuccess && (
                  <div role="status" className="mt-2.5 p-2 rounded-lg bg-teal-50 border border-teal-200 text-xs text-teal-800">
                    Work area updated successfully. Reflects immediately across zone analytics and reports.
                  </div>
                )}

                {editingArea && (
                  <form onSubmit={saveWorkArea} className="mt-3 pt-3 border-t border-slate-100 space-y-2">
                    <label className="block text-xs font-semibold text-slate-700">
                      Work Area Name
                      <input
                        autoFocus
                        type="text"
                        maxLength={255}
                        value={areaDraft}
                        onChange={(e) => setAreaDraft(e.target.value)}
                        placeholder="e.g. Zone 4 - Scaffolding"
                        className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                      />
                    </label>
                    <div className="flex items-center gap-2">
                      <button
                        type="submit"
                        disabled={areaSaving || !areaDraft.trim()}
                        className="px-3.5 py-1.5 rounded-lg bg-teal-700 hover:bg-teal-800 text-white text-xs font-semibold disabled:opacity-50 transition-colors"
                      >
                        {areaSaving ? 'Saving…' : 'Save Area'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingArea(false);
                          setAreaError(null);
                        }}
                        className="px-3 py-1.5 rounded-lg border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-semibold transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                    {areaError && (
                      <p role="alert" className="text-xs text-rose-700">
                        {areaError}
                      </p>
                    )}
                  </form>
                )}
              </div>

              {/* Observation Submission Context Grid */}
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-2.5">
                  Submission Context & Metadata
                </span>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block text-[11px]">Capture Source</span>
                    <span className="font-semibold text-slate-800 truncate block mt-0.5">
                      {obs.source === 'image_upload:site_image' ? 'Site Image' : obs.source}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">People Context</span>
                    <span className="font-semibold text-slate-800 block mt-0.5">
                      {obs.people_count != null ? `${obs.people_count} exposed` : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Exposure Duration</span>
                    <span className="font-semibold text-slate-800 block mt-0.5">
                      {obs.duration_minutes != null ? `${obs.duration_minutes} min` : '—'}
                    </span>
                  </div>
                  <div>
                    <span className="text-slate-400 block text-[11px]">Repetition Context</span>
                    <span className="font-semibold text-slate-800 block mt-0.5">
                      {obs.repeated_count != null ? `${obs.repeated_count} reps` : '—'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Overall Decision Snapshot Panel */}
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-2xs">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-2">
                  Observation Safety Decision Snapshot
                </span>
                {pendingCount > 0 ? <p role="status" className="text-xs text-amber-800">{completedAssessments.length} of {currentAssessments.length} assessments completed — {pendingCount} remaining. Final observation result will appear when all findings are complete.</p> : decision ? (
                  <SafetyDecisionPanel decision={decision} compact />
                ) : (
                  <p className="text-xs text-slate-500 italic">
                    Decision snapshot unavailable for this historical observation.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Section 2: Detected Hazards & Individual Assessments */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <h5 className="font-bold text-slate-800 uppercase tracking-wider text-xs flex items-center gap-2">
                <ShieldAlert size={15} className="text-teal-700" />
                <span>Detected PPE Findings & Risk Assessments ({obs.detected_hazards.length})</span>
              </h5>
              <span className="text-xs text-slate-500">
                Latest assessment per hazard contributes to risk intelligence.
              </span>
            </div>

            {obs.detected_hazards.length === 0 ? (
              <div className="p-5 rounded-xl border border-slate-200 bg-white text-center">
                <Shield size={24} className="text-slate-300 mx-auto mb-1.5" />
                <p className="text-xs font-semibold text-slate-700">No supported PPE violations recorded</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  This observation has no recorded PPE violations. This reflects model findings and does not certify absolute site safety.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {obs.detected_hazards.map((hazard, hIdx) => {
                  const latest = getLatestAssessment(hazard.assessments);
                  const ass = hazard.assessments.find(a => String(a.assessment_id) === highlightedAssessmentId) ?? latest;
                  const editable = canManage && ass === latest;
                  const isHighlighted =
                    highlightedAssessmentId &&
                    ass?.assessment_id &&
                    String(ass.assessment_id) === highlightedAssessmentId;
                  const isPending = ass?.status === 'pending' || ass == null;
                  const bandStyle = formatRiskBand(ass?.risk_band);

                  return (
                    <div
                      key={hazard.detected_hazard_id || hIdx}
                      id={`assessment-${ass?.assessment_id}`}
                      tabIndex={-1}
                      className={`p-4 rounded-xl border transition-all ${
                        isHighlighted
                          ? 'border-teal-500 bg-teal-50/30 ring-2 ring-teal-500/40'
                          : isPending
                          ? 'border-amber-200 bg-amber-50/30'
                          : 'border-slate-200 bg-white'
                      }`}
                    >
                      {/* Hazard Header */}
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex items-center gap-2">
                            <h6 className="font-bold text-slate-900 text-sm">
                              {formatHazardType(hazard.hazard_type)}
                            </h6>
                            {isHighlighted && (
                              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-600 text-white">
                                Target Assessment
                              </span>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500 mt-1">
                            <span>
                              Confidence:{' '}
                              <strong className="text-slate-700 font-mono">
                                {formatConfidence(hazard.detection_confidence)}
                              </strong>
                            </span>
                            <span>·</span>
                            <span>
                              Source label:{' '}
                              <span className="font-mono text-slate-600">{hazard.source_label}</span>
                            </span>
                            {ass?.assessment_id && (
                              <>
                                <span>·</span>
                                <span className="font-mono text-slate-500">
                                  Assessment #{ass.assessment_id} (v{ass.assessment_version})
                                </span>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Status / Band Badge */}
                        <div className="text-right">
                          {isPending ? (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-900 border border-amber-300">
                              <Clock size={13} className="text-amber-700" />
                              <span>Pending Operator Context</span>
                            </span>
                          ) : (
                            <div className="flex flex-col items-end">
                              <span
                                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold border ${bandStyle.badgeClass}`}
                              >
                                <span className={`w-2 h-2 rounded-full ${bandStyle.dotClass}`} />
                                <span>{bandStyle.label} Risk</span>
                                <span>({ass?.risk_score})</span>
                              </span>
                              <span className="text-[11px] text-slate-500 mt-1">
                                {ass?.severity} × {ass?.likelihood} × {ass?.exposure} = {ass?.risk_score}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Missing inputs note if pending */}
                      {isPending && ass?.missing_inputs && ass.missing_inputs.length > 0 && (
                        <div className="mt-2.5 p-2.5 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
                          <strong>Missing required inputs:</strong> {ass.missing_inputs.join(', ')}.
                        </div>
                      )}

                      {/* Pending Assessment Completion Form */}
                      {isPending && ass?.assessment_id != null && editable && (
                        <div className="mt-3">
                          <PendingAssessmentCompletion
                            observation={obs}
                            assessment={ass}
                            onCompleted={(result) => {
                              setConfirmations(current => ({ ...current, [result.assessment_id]: result }));
                              setLastCompletion(result);
                              onAssessmentUpdated(result.observation_id);
                            }}
                          />
                        </div>
                      )}

                      {/* Assessment Context Editor (Phase 8.1A Context Editing) */}
                      {!isPending && ass?.assessment_id != null && editable && (
                        <div className="mt-3 pt-3 border-t border-slate-100">
                          <AssessmentContextEditor
                            assessmentId={ass.assessment_id}
                            onSaved={() => {
                              setLastCompletion(null);
                              onAssessmentUpdated(obs.observation_id);
                            }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Last Completion alert notice */}
            {lastCompletion?.observation_id === obs.observation_id && (
              <div className="mt-4 p-4 rounded-xl border border-teal-200 bg-teal-50 text-teal-900 space-y-2">
                <p className="font-bold text-sm">
                  Assessment #{lastCompletion.assessment_id} Completed Successfully!
                </p>
                <p className="text-xs">
                  Severity {lastCompletion.assessment.severity} × likelihood {lastCompletion.assessment.likelihood} × exposure {lastCompletion.assessment.exposure} = risk score {lastCompletion.assessment.risk_score} ({lastCompletion.assessment.risk_band}).
                </p>
                {lastCompletion.alert_ids.length > 0 && (
                  <p className="text-xs font-medium">
                    Actionable Alert #{lastCompletion.alert_ids.join(', #')} created/linked in Alert Register.
                  </p>
                )}
                {lastCompletion.safety_decision.outcome === 'pending' && (
                  <p className="text-xs text-amber-800">
                    Other findings in this observation still require assessment.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
