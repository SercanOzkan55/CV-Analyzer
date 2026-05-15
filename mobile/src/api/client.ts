import Constants from 'expo-constants';

// adb reverse tcp:8001 tcp:8001 enables localhost access from emulator
const API_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8001';

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE';

interface RequestOptions {
  method?: Method;
  body?: any;
  token?: string | null;
  isFormData?: boolean;
  timeout?: number;
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T = any>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, token, isFormData = false, timeout = 60000 } = opts;

  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!isFormData) headers['Content-Type'] = 'application/json';

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: isFormData ? body : body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = Array.isArray(err.detail)
        ? err.detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; ')
        : err.detail;
      throw new ApiError(detail || `Request failed: ${res.status}`, res.status);
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return res.json();
    }
    return res.text() as any;
  } finally {
    clearTimeout(timer);
  }
}

// ── Auth (handled by Supabase client in AuthContext) ─────────────────────────

export function getProfile(token: string) {
  return request('/api/v1/profile', { token });
}

export function getUsage(token: string) {
  return request('/api/v1/usage', { token });
}

// ── CV Analysis ──────────────────────────────────────────────────────────────
export function analyzeCV(token: string, cvText: string, jobDescription: string, lang = '') {
  return request('/api/v1/analyze', {
    method: 'POST',
    token,
    body: { cv_text: cvText, job_description: jobDescription, lang },
  });
}

export function analyzePdf(token: string, formData: FormData) {
  return request('/api/v1/analyze-pdf', {
    method: 'POST',
    token,
    body: formData,
    isFormData: true,
    timeout: 120000,
  });
}

// ── History ──────────────────────────────────────────────────────────────────
export function getHistory(token: string) {
  return request('/api/v1/history', { token });
}

export function getAnalysisDetail(token: string, analysisId: number) {
  return request(`/api/v1/history/${analysisId}`, { token });
}

// ── Recruiter ────────────────────────────────────────────────────────────────
export function recruiterListJobs(token: string) {
  return request('/api/v1/recruiter/jobs', { token });
}

export function recruiterCreateJob(token: string, payload: { title: string; description: string }) {
  return request('/api/v1/recruiter/jobs', { method: 'POST', token, body: payload });
}

export function recruiterBatchRank(token: string, formData: FormData) {
  return request('/api/v1/recruiter/batch-rank', {
    method: 'POST',
    token,
    body: formData,
    isFormData: true,
    timeout: 300000,
  });
}

export function recruiterDashboardRank(token: string, payload: any) {
  return request('/api/v1/recruiter/dashboard/rank', { method: 'POST', token, body: payload });
}

export function recruiterDashboardPreview(token: string, payload: any) {
  return request('/api/v1/recruiter/dashboard/preview', { method: 'POST', token, body: payload });
}

export function recruiterDashboardAction(token: string, payload: any) {
  return request('/api/v1/recruiter/dashboard/action', { method: 'POST', token, body: payload });
}

export function recruiterDashboardActions(token: string, jobId: number) {
  return request(`/api/v1/recruiter/dashboard/actions/${jobId}`, { token });
}

export function recruiterListTemplates(token: string) {
  return request('/api/v1/recruiter/templates', { token });
}

export function recruiterCreateTemplate(token: string, payload: any) {
  return request('/api/v1/recruiter/templates', { method: 'POST', token, body: payload });
}

export function recruiterDeleteTemplate(token: string, templateId: number) {
  return request(`/api/v1/recruiter/templates/${templateId}`, { method: 'DELETE', token });
}

export function recruiterSendEmail(token: string, payload: any) {
  return request('/api/v1/recruiter/send-email', { method: 'POST', token, body: payload });
}

// ── Candidates ───────────────────────────────────────────────────────────────
export function recruiterCandidates(token: string) {
  return request('/api/v1/recruiter/candidates', { token });
}

export function recruiterTopCandidates(token: string) {
  return request('/api/v1/recruiter/top_candidates', { token });
}

export function recruiterCandidateDetail(token: string, analysisId: number) {
  return request(`/api/v1/recruiter/candidate/${analysisId}`, { token });
}

export function recruiterSearch(token: string, payload: any) {
  return request('/api/v1/recruiter/search', { method: 'POST', token, body: payload });
}

// ── Camera CV Scan ───────────────────────────────────────────────────────
export function scanCV(token: string, formData: FormData) {
  return request('/api/v1/recruiter/scan-cv', {
    method: 'POST',
    token,
    body: formData,
    isFormData: true,
    timeout: 120000,
  });
}

export { ApiError };
