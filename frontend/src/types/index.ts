export type RiskBand = 'Low' | 'Moderate' | 'High' | 'Critical';
export type UserRole = 'user' | 'safety_officer' | 'admin';

export interface AuthUser {
  user_id: string;
  email: string;
  role: UserRole;
}

export interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface DetectedHazardResponse {
  observation_id: string;
  hazard_type: string;
  source_label: string;
  detection_confidence: number | null;
}

export interface AssessmentResponse {
  observation_id: string;
  hazard_type: string;
  source_label: string;
  severity: number;
  likelihood: number;
  exposure: number;
  risk_score: number;
  risk_band: RiskBand;
  detection_confidence: number | null;
  explanation: string;
}

export type SafetyDecisionOutcome = 'alert' | 'warning' | 'no_alert' | 'pending';

export interface DecisionEvidenceResponse {
  hazard_type: string;
  source_label: string;
  detection_confidence: number | null;
  risk_score: number | null;
  risk_band: RiskBand | null;
}

export interface SafetyDecisionResponse {
  outcome: SafetyDecisionOutcome;
  reason: string;
  risk_band: RiskBand | null;
  priority: string;
  supporting_evidence: DecisionEvidenceResponse[];
  policy_version: string;
}

export interface AssessmentsResponse {
  observation_id: string;
  detected_hazards: DetectedHazardResponse[];
  assessments: AssessmentResponse[];
  pending_hazards: DetectedHazardResponse[];
  safety_decision: SafetyDecisionResponse;
  annotated_image?: string | null;
}

export interface PersistedAssessmentResponse {
  assessment_id?: number | null;
  assessment_version: number;
  status: 'pending' | 'completed';
  severity?: number | null;
  likelihood?: number | null;
  exposure?: number | null;
  risk_score?: number | null;
  risk_band?: RiskBand | null;
  explanation?: string | null;
  missing_inputs?: string[] | null;
  scoring_rule_version: string;
  assessed_at?: string | null;
  created_at?: string | null;
}

export interface PendingAssessmentContext {
  people_count?: number;
  duration_minutes?: number;
  repeated_count?: number;
}

export type AssessmentFilter = 'All' | 'Pending' | RiskBand;
export type AssessmentCounts = Record<Exclude<AssessmentFilter, 'All'>, number>;
export interface ObservationFilters {
  risk?: AssessmentFilter;
  work_area?: string;
  start?: string;
  end?: string;
  observation_id?: string;
  sort?: 'newest' | 'oldest';
  limit?: number;
  offset?: number;
}
export interface ObservationQueryResponse {
  items: (ObservationDetailResponse & { assessment_counts: AssessmentCounts })[];
  total: number;
  limit: number;
  offset: number;
  assessment_counts: AssessmentCounts;
  observation_counts: AssessmentCounts;
  unfiltered_risk_total: number;
}
export interface AssessmentContextResponse {
  observation_id: string;
  detected_hazard_id: number;
  assessment_id: number;
  revision: number;
  context: { people_count: number | null; duration_minutes: number | null; repeated_count: number | null };
  assessment: PersistedAssessmentResponse;
  safety_decision: SafetyDecisionResponse;
  audit_history: AssessmentCorrectionAudit[];
  reconciliation: { review_required: boolean; alert_ids: number[]; reason: string | null; state: 'review_required' | 'linked' | 'deferred_pending' | 'unchanged' };
}
export interface AssessmentCorrectionAudit {
  assessment_id: number;
  revision: number;
  previous_values: AssessmentContextResponse['context'];
  updated_values: Required<PendingAssessmentContext>;
  previous_result: { status: string; risk_score: number | null; risk_band: RiskBand | null };
  updated_result: { status: string; risk_score: number; risk_band: RiskBand };
  previous_decision: SafetyDecisionResponse;
  updated_decision: SafetyDecisionResponse;
  previous_observation_decision: SafetyDecisionResponse | null;
  updated_observation_decision: SafetyDecisionResponse;
  changed_by_user_id: string;
  changed_at: string;
}

export interface AssessmentCompletionResponse {
  assessment_id: number;
  observation_id: string;
  hazard_type: string;
  source_label: string;
  people_count: number;
  duration_minutes: number;
  repeated_count: number;
  assessment: PersistedAssessmentResponse;
  safety_decision: SafetyDecisionResponse;
  alert_id: number | null;
  alert_ids: number[];
  completion_audit: {
    previous_status: 'pending';
    completed_at: string;
    completed_by_user_id: string;
    provided_context: PendingAssessmentContext;
    new_context: PendingAssessmentContext;
    resolved_context: Required<PendingAssessmentContext>;
  };
}

export interface PersistedHazardResponse {
  detected_hazard_id?: number | null;
  hazard_type: string;
  source_label: string;
  detection_confidence?: number | null;
  detected_at?: string | null;
  detector_name?: string | null;
  evidence?: Record<string, unknown> | null;
  assessments: PersistedAssessmentResponse[];
}

export interface ObservationDetailResponse {
  observation_id: string;
  observed_at: string;
  source: string;
  work_area?: string | null;
  people_count?: number | null;
  duration_minutes?: number | null;
  repeated_count?: number | null;
  detection_confidence?: number | null;
  raw_metadata?: Record<string, unknown> | null;
  created_at?: string | null;
  updated_at?: string | null;
  detected_hazards: PersistedHazardResponse[];
}

export interface ExperimentalDetectionItem {
  class_name: string;
  confidence: number;
  box: [number, number, number, number];
  class_id?: number | null;
  is_hazard: boolean;
}

export interface ExperimentalSafetyFinding {
  hazard_type: string;
  source_label: string;
  confidence?: number | null;
}

export interface ExperimentalRecommendation {
  hazard_type: string;
  recommendation_text: string;
  priority: string;
  status: string;
}

export interface ExperimentalAlertDecision {
  alert_recommended: boolean;
  reason: string;
  priority: string;
}

export interface ExperimentalSafetyDetectResponse {
  image_width: number;
  image_height: number;
  detections: ExperimentalDetectionItem[];
  detected_hazards: ExperimentalSafetyFinding[];
  assessments: AssessmentResponse[];
  recommendations: ExperimentalRecommendation[];
  alert: ExperimentalAlertDecision;
  safety_decision: SafetyDecisionResponse;
  routing_decision: 'safety_review_required' | 'no_supported_ppe_violations' | 'assessment_pending';
  routing_status: 'review_required' | 'no_findings' | 'pending';
  routing_reason: string;
  is_risk_assessed: boolean;
  status_note: string;
}

export interface ImageAssessmentParams {
  observation_id?: string;
  work_area?: string;
  people_count?: number;
  duration_minutes?: number;
  repeated_count?: number;
}

export interface AlertObservationSummary {
  observation_id: string;
  observed_at: string;
  source: string;
  work_area?: string | null;
}

export interface AlertViolationSummary {
  detected_hazard_id: number;
  hazard_type: string;
  source_label: string;
  confidence?: number | null;
  detected_at: string;
  evidence?: Record<string, unknown> | null;
}

export interface AlertAssessmentSummary {
  assessment_id: number;
  status: 'pending' | 'completed';
  risk_score?: number | null;
  risk_band?: RiskBand | null;
}

export type AlertStatus = 'open' | 'acknowledged' | 'resolved' | 'dismissed';

export interface AlertDetailResponse {
  review_required: boolean;
  reconciliation_reason: string | null;
  current_assessment: AlertAssessmentSummary | null;
  alert_id: number;
  observation_id: string;
  detected_hazard_id?: number | null;
  assessment_id?: number | null;
  alert_type: string;
  message: string;
  risk_band?: RiskBand | null;
  status: AlertStatus;
  recipient?: string | null;
  created_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  dismissed_at?: string | null;
  observation: AlertObservationSummary;
  violation?: AlertViolationSummary | null;
  assessment?: AlertAssessmentSummary | null;
}

export interface AnalyticsViolationMetric {
  violation_type: string;
  count: number;
  observation_ids: string[];
  detected_hazard_ids: number[];
}

export interface AnalyticsAreaMetric {
  work_area: string;
  violation_count: number;
  most_common_violation?: AnalyticsViolationMetric | null;
  observation_ids: string[];
  detected_hazard_ids: number[];
}

export interface SafetyAnalyticsResponse {
  total_violations: number;
  violations_by_work_area: AnalyticsAreaMetric[];
  highest_violation_area?: AnalyticsAreaMetric | null;
  lowest_violation_area?: AnalyticsAreaMetric | null;
  most_common_violation?: AnalyticsViolationMetric | null;
  most_common_violation_by_area: AnalyticsAreaMetric[];
  risk_level_distribution: Record<'Low' | 'Moderate' | 'High' | 'Critical' | 'pending', number>;
  open_alert_count: number;
  unresolved_alert_count: number;
  resolved_alert_count: number;
  zone_identifier_source: string;
  zone_identifier_is_validated_entity: boolean;
  zone_identifier_note: string;
}

export interface WorkAreaRecurrenceGroup {
  work_area: string;
  hazard_type: string;
  observation_count: number;
  is_repeated: boolean;
  observation_ids: string[];
}

export interface WorkAreaObservationMetric {
  work_area: string;
  observation_count: number;
  observation_ids: string[];
}

export interface WorkAreaRecurrenceResponse {
  window_start: string | null;
  window_end: string | null;
  groups: WorkAreaRecurrenceGroup[];
  work_areas_by_observation_count: WorkAreaObservationMetric[];
  repeated_work_area_count: number;
  counting_unit: string;
  informational_only: boolean;
  work_area_note: string;
}

export interface SafetyReport {
  generated_at: string;
  generated_by: { email: string; role: UserRole };
  scope: { window_start: string | null; window_end: string | null; all_work_areas: boolean; work_areas: string[]; include_unassigned: boolean };
  summary: { total_observations: number; supported_ppe_findings: number; actionable_alerts: number; warnings: number; pending_assessments: number; resolved_alerts: number };
  decision_counts: Record<'alert' | 'warning' | 'pending' | 'no_alert' | 'unavailable', number>;
  risk_distribution: Record<'Low' | 'Moderate' | 'High' | 'Critical' | 'pending', number>;
  violation_breakdown: { hazard_type: string; count: number }[];
  work_areas: { work_area: string; violation_count: number; most_common_violation: string | null }[];
  highest_violation_work_areas: string[];
  recurrence: { work_area: string; hazard_type: string; observation_count: number; observation_ids: string[] }[];
  repeated_work_area_count: number;
  alert_status_counts: Record<AlertStatus, number>;
  alerts: { alert_id: number; observation_id: string; work_area: string; hazard_type: string | null; risk_band: string | null; status: AlertStatus; created_at: string; acknowledged_at: string | null; resolved_at: string | null; dismissed_at: string | null }[];
  findings: { observation_id: string; observed_at: string; work_area: string; detected_hazard_id: number; hazard_type: string; detection_confidence: number | null; assessment_status: string; risk_score: number | null; risk_band: string | null; safety_decision: string; alert_status: string | null }[];
  disclaimer: string;
}

export interface SafetyReportFilters {
  start?: string;
  end?: string;
  scope: 'all' | 'selected';
  workAreas: string[];
  includeUnassigned: boolean;
}
