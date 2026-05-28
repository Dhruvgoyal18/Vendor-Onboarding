// API Types for the Vendor Onboarding System

export type TaxIdType = "VAT" | "EIN" | "GST" | "PAN" | "GSTIN" | "OTHER";

export type SubmissionStatus = "processing" | "pending" | "approved" | "rejected" | "error";

export type StageStatus = "pending" | "running" | "completed" | "failed" | "skipped";

export type PipelineStageKey =
  | "intake"
  | "extract_fields"
  | "format_check"
  | "external_verification"
  | "extract_docs"
  | "cross_doc_check"
  | "merge"
  | "check_completeness"
  | "check_consistency"
  | "check_credibility"
  | "decide"
  | "output"
  | "done";

export interface PipelineStage {
  stage: PipelineStageKey;
  status: StageStatus;
  message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Document {
  id: string;
  document_type: string;
  storage_key: string | null;
  original_filename: string | null;
  extracted_json: Record<string, unknown> | null;
  extraction_confidence: number | null;
  ocr_status: "unknown" | "success" | "partial" | "failed";
  ocr_issues: string[] | null;
  created_at: string;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  actor: string | null;
  actor_role: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface EmailLog {
  id: string;
  recipient: string;
  subject: string;
  body: string | null;
  email_type: string | null;
  sent_at: string;
  success: boolean;
}

export interface VendorVersion {
  run_id: string;
  version_number: number;
  created_at: string;
  status: SubmissionStatus;
  decision_summary: string | null;
  resubmission_notes: string | null;
}

export interface ValidationResult {
  id: string;
  category: string;
  check_name: string;
  status: string;
  detail: string | null;
  confidence: number | null;
}

export interface Vendor {
  id: string;
  run_id: string;
  company_name: string;
  registration_number: string | null;
  country: string | null;
  contact_name: string | null;
  contact_email: string | null;
  tax_id: string | null;
  bank_account_name: string | null;
  bank_country: string | null;
  status: SubmissionStatus;
  current_stage: PipelineStageKey | null;
  decision_summary: string | null;
  risk_level: string | null;
  is_duplicate: boolean;
  duplicate_of_run_id: string | null;
  version_number: number;
  original_run_id: string | null;
  created_at: string;
  updated_at: string | null;
  decided_at: string | null;
}

export interface VendorDetail extends Vendor {
  // Detail-only fields
  incorporation_date: string | null;
  tax_id_type: string | null;
  bank_name: string | null;
  cin_number: string | null;
  pan_number: string | null;
  gstin_number: string | null;
  ifsc_code: string | null;
  account_type: string | null;
  registered_state: string | null;
  sla_due_at: string | null;
  override_by: string | null;
  override_at: string | null;
  override_reason: string | null;
  pipeline_duration_ms: number | null;
  // Related objects
  documents: Document[];
  validation_results: ValidationResult[];
  pipeline_stages: PipelineStage[];
  merged_data: Record<string, unknown> | null;
  email_logs: EmailLog[];
  audit_events: AuditEvent[];
}

export interface DashboardStats {
  total: number;
  approved: number;
  pending: number;
  rejected: number;
  processing: number;
  error: number;
}

export interface PaginatedVendors {
  items: Vendor[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface SubmissionFormData {
  // Core (all countries)
  company_name: string;
  registration_number: string;
  country: string;
  incorporation_date: string;
  contact_name: string;
  contact_email: string;
  tax_id?: string;
  tax_id_type?: string;
  bank_account_name: string;
  account_number: string;
  bank_name: string;
  bank_country: string;
  // India-specific
  cin_number?: string;
  pan_number?: string;
  gstin_number?: string;
  ifsc_code?: string;
  account_type?: string;
  registered_state?: string;
}

export interface SSEUpdate {
  run_id: string;
  status: SubmissionStatus;
  current_stage: PipelineStageKey | null;
  stages: PipelineStage[];
  decision_summary: string | null;
  risk_level: string | null;
}

export const STAGE_LABELS: Record<PipelineStageKey, string> = {
  intake: "Intake",
  extract_fields: "Extracting Fields",
  format_check: "Format Checks (Layer 1)",
  external_verification: "External Registry Verification",
  extract_docs: "Extracting Documents",
  cross_doc_check: "Cross-Document Checks (Layer 3)",
  merge: "Merging Data",
  check_completeness: "Completeness Check",
  check_consistency: "Consistency Analysis",
  check_credibility: "Credibility Analysis",
  decide: "Making Decision",
  output: "Generating Output",
  done: "Complete",
};

export const COUNTRY_TAX_DEFAULTS: Record<string, { type: string; label: string }> = {
  GB: { type: "VAT", label: "UK VAT Number (GB + 9 digits)" },
  US: { type: "EIN", label: "EIN (XX-XXXXXXX)" },
  IN: { type: "GSTIN", label: "GSTIN (15 characters, e.g. 29AAACI1681G1ZK)" },
  AU: { type: "ABN", label: "ABN (11 digits)" },
  DE: { type: "VAT", label: "German VAT (DE + 9 digits)" },
  FR: { type: "VAT", label: "French VAT" },
  CA: { type: "GST", label: "Canadian GST/HST" },
};

// ─── India States ─────────────────────────────────────────────────────────────
export const INDIA_STATES: { code: string; name: string; gstCode: string }[] = [
  { code: "JK", name: "Jammu and Kashmir", gstCode: "01" },
  { code: "HP", name: "Himachal Pradesh", gstCode: "02" },
  { code: "PB", name: "Punjab", gstCode: "03" },
  { code: "CH", name: "Chandigarh", gstCode: "04" },
  { code: "UK", name: "Uttarakhand", gstCode: "05" },
  { code: "HR", name: "Haryana", gstCode: "06" },
  { code: "DL", name: "Delhi", gstCode: "07" },
  { code: "RJ", name: "Rajasthan", gstCode: "08" },
  { code: "UP", name: "Uttar Pradesh", gstCode: "09" },
  { code: "BR", name: "Bihar", gstCode: "10" },
  { code: "SK", name: "Sikkim", gstCode: "11" },
  { code: "AR", name: "Arunachal Pradesh", gstCode: "12" },
  { code: "NL", name: "Nagaland", gstCode: "13" },
  { code: "MN", name: "Manipur", gstCode: "14" },
  { code: "MZ", name: "Mizoram", gstCode: "15" },
  { code: "TR", name: "Tripura", gstCode: "16" },
  { code: "ML", name: "Meghalaya", gstCode: "17" },
  { code: "AS", name: "Assam", gstCode: "18" },
  { code: "WB", name: "West Bengal", gstCode: "19" },
  { code: "JH", name: "Jharkhand", gstCode: "20" },
  { code: "OD", name: "Odisha", gstCode: "21" },
  { code: "CT", name: "Chhattisgarh", gstCode: "22" },
  { code: "MP", name: "Madhya Pradesh", gstCode: "23" },
  { code: "GJ", name: "Gujarat", gstCode: "24" },
  { code: "DD", name: "Dadra and Nagar Haveli and Daman and Diu", gstCode: "26" },
  { code: "MH", name: "Maharashtra", gstCode: "27" },
  { code: "AP", name: "Andhra Pradesh", gstCode: "28" },
  { code: "KA", name: "Karnataka", gstCode: "29" },
  { code: "GA", name: "Goa", gstCode: "30" },
  { code: "KL", name: "Kerala", gstCode: "32" },
  { code: "TN", name: "Tamil Nadu", gstCode: "33" },
  { code: "PY", name: "Puducherry", gstCode: "34" },
  { code: "TS", name: "Telangana", gstCode: "36" },
  { code: "LA", name: "Ladakh", gstCode: "38" },
];

// ─── IFSC Bank Code Map ───────────────────────────────────────────────────────
export const IFSC_BANK_CODES: Record<string, string> = {
  HDFC: "HDFC Bank",
  ICIC: "ICICI Bank",
  SBIN: "State Bank of India",
  KKBK: "Kotak Mahindra Bank",
  UTIB: "Axis Bank",
  PUNB: "Punjab National Bank",
  CNRB: "Canara Bank",
  UBIN: "Union Bank of India",
  BARB: "Bank of Baroda",
  IOBA: "Indian Overseas Bank",
  BKID: "Bank of India",
  INDB: "IndusInd Bank",
  YESB: "Yes Bank",
  IDFC: "IDFC First Bank",
  AUBL: "AU Small Finance Bank",
  FDRL: "Federal Bank",
};
