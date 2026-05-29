import {
  DashboardStats,
  PaginatedVendors,
  SubmissionFormData,
  VendorDetail,
  VendorVersion,
  SSEUpdate,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Token helpers ────────────────────────────────────────────────────────────

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^| )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[2]) : null;
}

async function refreshToken(role: "admin" | "vendor"): Promise<boolean> {
  const res = await fetch(`/api/${role}/refresh`, { method: "POST" });
  return res.ok;
}

// ─── Core fetch wrapper ───────────────────────────────────────────────────────

export async function apiRequest<T>(
  path: string,
  options?: RequestInit & { auth?: "admin" | "vendor" }
): Promise<T> {
  const { auth, ...fetchOptions } = options ?? {};
  const url = `${API_BASE}${path}`;

  const doFetch = (token: string | null) =>
    fetch(url, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(fetchOptions.headers ?? {}),
      },
      ...fetchOptions,
    });

  const token = auth ? getCookie(`${auth}_access_token`) : null;
  let response = await doFetch(token);

  // On 401 try to refresh once and retry
  if (response.status === 401 && auth) {
    const refreshed = await refreshToken(auth);
    if (refreshed) {
      const newToken = getCookie(`${auth}_access_token`);
      response = await doFetch(newToken);
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

// ─── Submission result type ───────────────────────────────────────────────────

export interface SubmissionResult {
  run_id: string;
  message: string;
  was_auto_versioned: boolean;
  existing_run_id: string | null;
}

export class AlreadyApprovedError extends Error {
  existingRunId: string;
  constructor(message: string, existingRunId: string) {
    super(message);
    this.name = "AlreadyApprovedError";
    this.existingRunId = existingRunId;
  }
}

// ─── Submissions ──────────────────────────────────────────────────────────────

export async function createSubmission(
  formData: SubmissionFormData,
  files: {
    registration?: File | null;
    bank?: File | null;
    tax?: File | null;
    pan_gstin?: File | null;
  }
): Promise<SubmissionResult> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(formData));
  if (files.registration) fd.append("registration_doc", files.registration);
  if (files.bank) fd.append("bank_doc", files.bank);
  if (files.tax) fd.append("tax_doc", files.tax);
  if (files.pan_gstin) fd.append("pan_gstin_doc", files.pan_gstin);

  const response = await fetch(`${API_BASE}/api/submissions`, {
    method: "POST",
    body: fd,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Submission failed" }));
    if (response.status === 409 && error.detail?.code === "ALREADY_APPROVED") {
      throw new AlreadyApprovedError(error.detail.message, error.detail.existing_run_id);
    }
    throw new Error(
      typeof error.detail === "string" ? error.detail : "Submission failed"
    );
  }
  return response.json();
}

export async function getSubmission(runId: string): Promise<VendorDetail> {
  return apiRequest<VendorDetail>(`/api/submissions/${runId}`);
}

export async function getVersions(runId: string): Promise<VendorVersion[]> {
  return apiRequest<VendorVersion[]>(`/api/submissions/${runId}/versions`);
}

export async function resubmitVendor(
  runId: string,
  formData: SubmissionFormData,
  files: {
    registration?: File | null;
    bank?: File | null;
    tax?: File | null;
    pan_gstin?: File | null;
  },
  resubmissionNotes?: string
): Promise<{ run_id: string; message: string }> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(formData));
  if (resubmissionNotes) fd.append("resubmission_notes", resubmissionNotes);
  if (files.registration) fd.append("registration_doc", files.registration);
  if (files.bank) fd.append("bank_doc", files.bank);
  if (files.tax) fd.append("tax_doc", files.tax);
  if (files.pan_gstin) fd.append("pan_gstin_doc", files.pan_gstin);

  const response = await fetch(`${API_BASE}/api/submissions/${runId}/resubmit`, {
    method: "POST",
    body: fd,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Resubmission failed" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }
  return response.json();
}

export async function getStages(runId: string) {
  return apiRequest<{
    run_id: string;
    status: string;
    current_stage: string | null;
    stages: Array<{
      stage: string;
      status: string;
      message: string | null;
      started_at: string | null;
      completed_at: string | null;
    }>;
  }>(`/api/submissions/${runId}/stages`);
}

export async function getMySubmissions() {
  return apiRequest<
    Array<{
      run_id: string;
      company_name: string;
      country: string;
      status: string;
      risk_level: string | null;
      created_at: string;
      decided_at: string | null;
      version_number: number;
    }>
  >("/api/submissions/mine", { auth: "vendor" });
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

export async function getDashboardStats(): Promise<DashboardStats> {
  return apiRequest<DashboardStats>("/api/dashboard/stats", { auth: "admin" });
}

export async function getDashboardHistory(params: {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
}): Promise<PaginatedVendors> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.status && params.status !== "all") query.set("status", params.status);
  if (params.search) query.set("search", params.search);

  return apiRequest<PaginatedVendors>(`/api/dashboard/history?${query}`, {
    auth: "admin",
  });
}

// ─── SSE ──────────────────────────────────────────────────────────────────────

const TERMINAL_STATUSES = new Set(["approved", "rejected", "pending", "error"]);

export function subscribeToRunEvents(
  runId: string,
  onUpdate: (data: SSEUpdate) => void,
  onError?: (error: Event) => void
): () => void {
  const url = `${API_BASE}/api/submissions/${runId}/events`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data: SSEUpdate = JSON.parse(event.data);
      onUpdate(data);
      if (TERMINAL_STATUSES.has(data.status)) {
        eventSource.close();
      }
    } catch (e) {
      console.error("Failed to parse SSE data:", e);
    }
  };

  eventSource.onerror = (error) => {
    onError?.(error);
  };

  return () => eventSource.close();
}
