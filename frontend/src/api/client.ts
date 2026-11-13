import type {
  AssessmentContextResponse,
  ObservationFilters,
  ObservationQueryResponse,
  AssessmentsResponse,
  AssessmentCompletionResponse,
  AlertDetailResponse,
  AuthUser,
  ExperimentalSafetyDetectResponse,
  ImageAssessmentParams,
  ObservationDetailResponse,
  PendingAssessmentContext,
  SafetyAnalyticsResponse,
  SafetyReport,
  SafetyReportFilters,
  TokenResponse,
  WorkAreaRecurrenceResponse,
} from '../types';

const TOKEN_KEY = 'safesite.access_token';

export async function queryObservations(filters: ObservationFilters = {}): Promise<ObservationQueryResponse> {
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value !== undefined) query.set(key, String(value)); });
  const res = await apiFetch(`/observation-query?${query}`);
  const contentType = res.headers.get('content-type')?.toLowerCase() ?? '';
  if (!contentType.includes('application/json')) {
    throw new ApiError(res.status, `Safety Incidents API returned a non-JSON response (HTTP ${res.status}). Check the /observation-query proxy to http://127.0.0.1:8000 and restart the frontend dev server if needed.`);
  }
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Unable to query observations'));
  try {
    return await res.json() as ObservationQueryResponse;
  } catch {
    throw new ApiError(res.status, 'Safety Incidents API returned invalid JSON. Check the backend response and try again.');
  }
}

export async function fetchAssessmentContext(id: number): Promise<AssessmentContextResponse> {
  const res = await apiFetch(`/assessments/${id}`);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Unable to load assessment'));
  return await res.json() as AssessmentContextResponse;
}

export async function correctAssessmentContext(id: number, expected_revision: number, context: Required<PendingAssessmentContext>): Promise<AssessmentContextResponse> {
  const res = await apiFetch(`/assessments/${id}/context`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_revision, ...context }),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Unable to correct assessment'));
  return await res.json() as AssessmentContextResponse;
}
const SESSION_EXPIRED_EVENT = 'safesite:session-expired';

export function getAccessToken(): string | null {
  return typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY);
}

export function storeAccessToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearAccessToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json() as { detail?: string | { message?: string } };
    if (typeof body.detail === 'string') return body.detail;
    return body.detail?.message || fallback;
  } catch {
    return fallback;
  }
}

export async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401) {
    clearAccessToken();
    window.dispatchEvent(new Event(SESSION_EXPIRED_EVENT));
  }
  return res;
}

export async function signup(email: string, password: string): Promise<AuthUser> {
  const res = await fetch('/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Signup failed'));
  return await res.json() as AuthUser;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Login failed'));
  return await res.json() as TokenResponse;
}

export async function fetchCurrentUser(): Promise<AuthUser> {
  const res = await apiFetch('/auth/me');
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Session is no longer valid'));
  return await res.json() as AuthUser;
}

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

  const res = await apiFetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    throw new ApiError(res.status, await parseError(res, `Assessment failed (HTTP ${res.status})`));
  }

  return (await res.json()) as AssessmentsResponse;
}

export async function fetchObservations(
  limit: number = 20,
  offset: number = 0
): Promise<ObservationsResult> {
  try {
    const res = await apiFetch(`/observations?limit=${limit}&offset=${offset}`);
    if (res.status === 401) throw new ApiError(401, 'Session expired');
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
  const res = await apiFetch(`/observations/${encodeURIComponent(observationId)}`);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, `Observation not found (HTTP ${res.status})`));
  return (await res.json()) as ObservationDetailResponse;
}

export async function updateObservationWorkArea(observationId: string, workArea: string): Promise<ObservationDetailResponse> {
  const res = await apiFetch(`/observations/${encodeURIComponent(observationId)}/work-area`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ work_area: workArea }),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to save work area'));
  return await res.json() as ObservationDetailResponse;
}

export async function completePendingAssessment(
  assessmentId: number,
  context: PendingAssessmentContext
): Promise<AssessmentCompletionResponse> {
  const res = await apiFetch(`/assessments/${assessmentId}/complete`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(context),
  });
  if (!res.ok) {
    let message = `Assessment completion failed (HTTP ${res.status})`;
    try {
      const body = await res.json() as { detail?: string | { message?: string } };
      if (typeof body.detail === 'string') message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      // Keep the HTTP fallback if the response is not JSON.
    }
    throw new ApiError(res.status, message);
  }
  return await res.json() as AssessmentCompletionResponse;
}

export function getObservationImageUrl(
  observationId: string,
  variant: 'original' | 'annotated'
): string {
  return `/observations/${encodeURIComponent(observationId)}/image/${variant}`;
}

export async function fetchObservationImage(
  observationId: string,
  variant: 'original' | 'annotated'
): Promise<string> {
  const res = await apiFetch(getObservationImageUrl(observationId, variant));
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Image unavailable'));
  return URL.createObjectURL(await res.blob());
}

export async function fetchAlerts(observationId?: string): Promise<AlertDetailResponse[]> {
  const url = observationId ? `/alerts?observation_id=${encodeURIComponent(observationId)}` : '/alerts';
  const res = await apiFetch(url);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to load alerts'));
  return await res.json() as AlertDetailResponse[];
}

export async function updateAlertStatus(
  alertId: number,
  status: 'acknowledged' | 'resolved' | 'dismissed'
): Promise<AlertDetailResponse> {
  const res = await apiFetch(`/alerts/${alertId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Alert update failed'));
  return await res.json() as AlertDetailResponse;
}

export async function fetchZoneAnalytics(): Promise<SafetyAnalyticsResponse> {
  const res = await apiFetch('/analytics/zones');
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to load zone analytics'));
  return await res.json() as SafetyAnalyticsResponse;
}

export async function fetchWorkAreaRecurrence(start?: string, end?: string): Promise<WorkAreaRecurrenceResponse> {
  const query = new URLSearchParams();
  if (start) query.set('start', start);
  if (end) query.set('end', end);
  const url = `/analytics/work-area-recurrence${query.size ? `?${query}` : ''}`;
  const res = await apiFetch(url);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to load work-area recurrence'));
  return await res.json() as WorkAreaRecurrenceResponse;
}

export async function fetchReportWorkAreas(): Promise<string[]> {
  const res = await apiFetch('/reports/work-areas');
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to load work areas'));
  return (await res.json() as { work_areas: string[] }).work_areas;
}

function reportQuery(filters: SafetyReportFilters): string {
  const query = new URLSearchParams();
  query.set('scope', filters.scope);
  if (filters.start) query.set('start', filters.start);
  if (filters.end) query.set('end', filters.end);
  if (filters.scope === 'selected') {
    filters.workAreas.forEach((name) => query.append('work_area', name));
    if (filters.includeUnassigned) query.set('include_unassigned', 'true');
  }
  return query.toString();
}

export async function fetchSafetyReport(filters: SafetyReportFilters): Promise<SafetyReport> {
  const res = await apiFetch(`/reports/safety?${reportQuery(filters)}`);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to generate report preview'));
  return await res.json() as SafetyReport;
}

export async function downloadSafetyReport(filters: SafetyReportFilters): Promise<void> {
  const res = await apiFetch(`/reports/safety.pdf?${reportQuery(filters)}`);
  if (!res.ok) throw new ApiError(res.status, await parseError(res, 'Failed to download PDF report'));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const disposition = res.headers.get('Content-Disposition') || '';
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || 'SafeSite_Safety_Report.pdf';
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; document.body.appendChild(anchor); anchor.click(); anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function submitExperimentalSafetyDetect(
  file: File,
  params?: ImageAssessmentParams
): Promise<ExperimentalSafetyDetectResponse> {
  const searchParams = new URLSearchParams();
  if (params?.work_area?.trim()) {
    searchParams.append('work_area', params.work_area.trim());
  }
  if (params?.people_count !== undefined && !isNaN(params.people_count)) {
    searchParams.append('people_count', params.people_count.toString());
  }
  if (params?.duration_minutes !== undefined && !isNaN(params.duration_minutes)) {
    searchParams.append('duration_minutes', params.duration_minutes.toString());
  }
  if (params?.repeated_count !== undefined && !isNaN(params.repeated_count)) {
    searchParams.append('repeated_count', params.repeated_count.toString());
  }

  const queryString = searchParams.toString();
  const url = `/experimental/safety/detect${queryString ? `?${queryString}` : ''}`;

  const formData = new FormData();
  formData.append('file', file, file.name);

  const res = await apiFetch(url, {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    let errorDetail = `Detection failed (HTTP ${res.status})`;
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

  return (await res.json()) as ExperimentalSafetyDetectResponse;
}
