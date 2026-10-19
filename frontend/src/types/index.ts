export type RiskBand = 'Low' | 'Moderate' | 'High' | 'Critical';

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

export interface AssessmentsResponse {
  observation_id: string;
  detected_hazards: DetectedHazardResponse[];
  assessments: AssessmentResponse[];
  pending_hazards: DetectedHazardResponse[];
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

export interface ImageAssessmentParams {
  observation_id?: string;
  work_area?: string;
  people_count?: number;
  duration_minutes?: number;
  repeated_count?: number;
}
