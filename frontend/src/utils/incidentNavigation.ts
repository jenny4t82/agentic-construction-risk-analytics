import type { ObservationFilters } from '../types';

export function incidentLink(observationId: string, assessmentId?: number, filters: ObservationFilters = {}): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined) params.set(key, String(value)); });
  params.set('observation_id', observationId);
  if (assessmentId !== undefined) params.set('assessment_id', String(assessmentId));
  return `#incidents?${params}`;
}

export function incidentTarget() {
  const params = new URLSearchParams(window.location.hash.split('?')[1] ?? '');
  return { observationId: params.get('observation_id'), assessmentId: params.get('assessment_id') };
}
