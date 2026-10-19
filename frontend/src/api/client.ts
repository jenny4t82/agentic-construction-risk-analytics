import type {
  AssessmentsResponse,
  ImageAssessmentParams,
  ObservationDetailResponse,
} from '../types';

export interface ObservationsResult {
  data: ObservationDetailResponse[];
  isDatabaseConfigured: boolean;
  error: string | null;
}

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const res = await fetch('/health', { method: 'GET' });
    if (!res.ok) return false;
    const body = await res.json();
    return body.status === 'ok';
  } catch {
    return false;
  }
}

export async function submitImageAssessment(
  file: File,
  params: ImageAssessmentParams
): Promise<AssessmentsResponse> {
  const searchParams = new URLSearchParams();
  if (params.observation_id?.trim()) {
    searchParams.append('observation_id', params.observation_id.trim());
  }
  if (params.work_area?.trim()) {
    searchParams.append('work_area', params.work_area.trim());
  }
  if (params.people_count !== undefined && !isNaN(params.people_count)) {
    searchParams.append('people_count', params.people_count.toString());
  }
  if (params.duration_minutes !== undefined && !isNaN(params.duration_minutes)) {
    searchParams.append('duration_minutes', params.duration_minutes.toString());
  }
  if (params.repeated_count !== undefined && !isNaN(params.repeated_count)) {
    searchParams.append('repeated_count', params.repeated_count.toString());
  }

  const queryString = searchParams.toString();
  const url = `/assessments/image${queryString ? `?${queryString}` : ''}`;

  const formData = new FormData();
  formData.append('file', file, file.name);

  const res = await fetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = `Assessment failed (HTTP ${res.status})`;
    try {
      const errJson = await res.json();
      if (errJson && errJson.detail) {
        errorDetail = errJson.detail;
      }
    } catch {
      // Non-JSON response
    }
    throw new Error(errorDetail);
  }

  return (await res.json()) as AssessmentsResponse;
}

export async function fetchObservations(
  limit: number = 20,
  offset: number = 0
): Promise<ObservationsResult> {
  try {
    const res = await fetch(`/observations?limit=${limit}&offset=${offset}`);
    if (res.status === 503) {
      return {
        data: [],
        isDatabaseConfigured: false,
        error: null,
      };
    }
    if (!res.ok) {
      let msg = `Failed to fetch observations (HTTP ${res.status})`;
      try {
        const body = await res.json();
        if (body.detail) msg = body.detail;
      } catch {
        // Fallback
      }
      return {
        data: [],
        isDatabaseConfigured: true,
        error: msg,
      };
    }
    const data = (await res.json()) as ObservationDetailResponse[];
    return {
      data,
      isDatabaseConfigured: true,
      error: null,
    };
  } catch (err) {
    return {
      data: [],
      isDatabaseConfigured: true,
      error: err instanceof Error ? err.message : 'Network error fetching observations',
    };
  }
}

export async function fetchObservationDetail(
  observationId: string
): Promise<ObservationDetailResponse> {
  const res = await fetch(`/observations/${encodeURIComponent(observationId)}`);
  if (!res.ok) {
    let msg = `Observation not found (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body.detail) msg = body.detail;
    } catch {
      // Fallback
    }
    throw new Error(msg);
  }
  return (await res.json()) as ObservationDetailResponse;
}
