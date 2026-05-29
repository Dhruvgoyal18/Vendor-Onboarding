"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { createSubmission, resubmitVendor, getSubmission } from "@/lib/api";
import { SubmissionFormData, COUNTRY_TAX_DEFAULTS, INDIA_STATES } from "@/lib/types";
import {
  validateCIN,
  validatePAN,
  validateGSTIN,
  validateIFSC,
  CIN_REGEX,
  PAN_REGEX,
  GSTIN_REGEX,
  IFSC_REGEX,
} from "@/lib/validators";
import {
  Upload,
  X,
  FileText,
  AlertCircle,
  Building2,
  User,
  CreditCard,
  Landmark,
  Loader2,
  CheckCircle,
  ChevronRight,
  Info,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react";

// ─── Countries list ──────────────────────────────────────────────────────────────
const COUNTRIES = [
  { code: "IN", name: "🇮🇳 India" },
  { code: "GB", name: "🇬🇧 United Kingdom" },
  { code: "US", name: "🇺🇸 United States" },
  { code: "DE", name: "🇩🇪 Germany" },
  { code: "FR", name: "🇫🇷 France" },
  { code: "AU", name: "🇦🇺 Australia" },
  { code: "CA", name: "🇨🇦 Canada" },
  { code: "SG", name: "🇸🇬 Singapore" },
  { code: "AE", name: "🇦🇪 United Arab Emirates" },
  { code: "JP", name: "🇯🇵 Japan" },
  { code: "NL", name: "🇳🇱 Netherlands" },
  { code: "SE", name: "🇸🇪 Sweden" },
  { code: "CH", name: "🇨🇭 Switzerland" },
  { code: "ZA", name: "🇿🇦 South Africa" },
  { code: "BR", name: "🇧🇷 Brazil" },
  { code: "OTHER", name: "Other" },
];

// ─── Live Validation Badges ────────────────────────────────────────────────────
function ValidationBadge({ status, message }: { status: "pass" | "fail" | "hint"; message: string }) {
  const colors = {
    pass: "bg-emerald-500/10 border-emerald-500/30 text-emerald-400",
    fail: "bg-red-500/10 border-red-500/30 text-red-400",
    hint: "bg-violet-500/10 border-violet-500/30 text-violet-400",
  };
  const icons = {
    pass: <CheckCircle className="w-3 h-3 flex-shrink-0" />,
    fail: <AlertTriangle className="w-3 h-3 flex-shrink-0" />,
    hint: <Info className="w-3 h-3 flex-shrink-0" />,
  };
  return (
    <div className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border mt-1.5 ${colors[status]}`}>
      {icons[status]}
      <span>{message}</span>
    </div>
  );
}

// ─── File Upload Zone ────────────────────────────────────────────────────────────
interface FileUploadZoneProps {
  label: string;
  description: string;
  file: File | null;
  onFileChange: (file: File | null) => void;
  required?: boolean;
  badge?: string;
}

function FileUploadZone({ label, description, file, onFileChange, required, badge }: FileUploadZoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files[0];
      if (dropped) onFileChange(dropped);
    },
    [onFileChange]
  );

  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-2">
        {label} {required && <span className="text-violet-400">*</span>}
        {badge && (
          <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-amber-500/15 text-amber-400 border border-amber-500/30 rounded-full">
            {badge}
          </span>
        )}
      </label>
      <div
        className={`upload-zone relative ${isDragging ? "dragover" : ""} ${file ? "has-file" : ""}`}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          className="hidden"
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                <FileText className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="min-w-0">
                <p className="text-sm text-emerald-300 font-medium truncate">{file.name}</p>
                <p className="text-xs text-slate-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
              </div>
            </div>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onFileChange(null); }}
              className="p-1.5 rounded-lg hover:bg-slate-700 text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ) : (
          <div className="py-2">
            <div className="w-8 h-8 rounded-lg bg-slate-700/60 flex items-center justify-center mx-auto mb-2">
              <Upload className="w-4 h-4 text-slate-400" />
            </div>
            <p className="text-sm text-slate-400 mb-0.5">
              Drop file or <span className="text-violet-400 hover:text-violet-300">browse</span>
            </p>
            <p className="text-xs text-slate-600">{description}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Form Field ──────────────────────────────────────────────────────────────────
interface FormFieldProps {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}

function FormField({ label, required, error, hint, children }: FormFieldProps) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1.5">
        {label} {required && <span className="text-violet-400">*</span>}
      </label>
      {children}
      {hint && !error && (
        <p className="text-xs text-slate-600 mt-1.5 flex items-center gap-1">
          <Info className="w-3 h-3" />
          {hint}
        </p>
      )}
      {error && (
        <p className="text-xs text-red-400 mt-1.5 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" />
          {error}
        </p>
      )}
    </div>
  );
}

// ─── Section Header ──────────────────────────────────────────────────────────────
function SectionHeader({
  icon: Icon, title, subtitle, badge,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  badge?: string;
}) {
  return (
    <div className="flex items-start gap-3 mb-6">
      <div className="w-9 h-9 rounded-xl bg-violet-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Icon className="w-[18px] h-[18px] text-violet-400" />
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-white font-semibold text-sm">{title}</h3>
          {badge && (
            <span className="text-[10px] px-2 py-0.5 bg-orange-500/15 text-orange-400 border border-orange-500/30 rounded-full font-medium">
              {badge}
            </span>
          )}
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>
      </div>
    </div>
  );
}

// ─── Main SubmissionForm Component ───────────────────────────────────────────────
export default function SubmissionForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resubmitRunId = searchParams.get("resubmit");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Partial<Record<string, string>>>({});
  const [resubmitNotes, setResubmitNotes] = useState("");
  const [isLoadingPrefill, setIsLoadingPrefill] = useState(!!resubmitRunId);

  const [form, setForm] = useState<SubmissionFormData>({
    company_name: "",
    registration_number: "",
    country: "",
    incorporation_date: "",
    contact_name: "",
    contact_email: "",
    tax_id: "",
    tax_id_type: "",
    bank_account_name: "",
    account_number: "",
    bank_name: "",
    bank_country: "",
    // India-specific
    cin_number: "",
    pan_number: "",
    gstin_number: "",
    ifsc_code: "",
    account_type: "",
    registered_state: "",
  });

  const [files, setFiles] = useState<{
    registration: File | null;
    bank: File | null;
    tax: File | null;
    pan_gstin: File | null;
  }>({
    registration: null,
    bank: null,
    tax: null,
    pan_gstin: null,
  });

  // Pre-fill form when resubmitting
  useEffect(() => {
    if (!resubmitRunId) return;
    getSubmission(resubmitRunId)
      .then((vendor) => {
        setForm({
          company_name: vendor.company_name || "",
          registration_number: vendor.registration_number || "",
          country: vendor.country || "",
          incorporation_date: vendor.incorporation_date || "",
          contact_name: vendor.contact_name || "",
          contact_email: vendor.contact_email || "",
          tax_id: vendor.tax_id || "",
          tax_id_type: vendor.tax_id_type || "",
          bank_account_name: vendor.bank_account_name || "",
          account_number: "",  // not returned by API for security
          bank_name: vendor.bank_name || "",
          bank_country: vendor.bank_country || "",
          cin_number: vendor.cin_number || "",
          pan_number: vendor.pan_number || "",
          gstin_number: vendor.gstin_number || "",
          ifsc_code: vendor.ifsc_code || "",
          account_type: vendor.account_type || "",
          registered_state: vendor.registered_state || "",
        });
      })
      .catch(() => {})
      .finally(() => setIsLoadingPrefill(false));
  }, [resubmitRunId]);

  const isIndia = form.country === "IN";

  const updateField = (field: keyof SubmissionFormData, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));

    if (field === "country") {
      const defaults = COUNTRY_TAX_DEFAULTS[value];
      if (defaults) {
        setForm((prev) => ({ ...prev, country: value, tax_id_type: defaults.type }));
      }
    }
  };

  const validate = (): boolean => {
    const newErrors: Partial<Record<string, string>> = {};

    if (!form.company_name.trim()) newErrors.company_name = "Required";
    if (!form.country) newErrors.country = "Required";
    if (!form.incorporation_date) newErrors.incorporation_date = "Required";
    if (!form.contact_name.trim()) newErrors.contact_name = "Required";

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!form.contact_email.trim()) newErrors.contact_email = "Required";
    else if (!emailPattern.test(form.contact_email)) newErrors.contact_email = "Invalid email format";

    if (!form.bank_account_name.trim()) newErrors.bank_account_name = "Required";
    if (!form.account_number.trim()) newErrors.account_number = "Required";
    if (!form.bank_name.trim()) newErrors.bank_name = "Required";
    if (!form.bank_country) newErrors.bank_country = "Required";

    if (isIndia) {
      if (!form.cin_number?.trim()) newErrors.cin_number = "Required for India";
      else if (!CIN_REGEX.test(form.cin_number.toUpperCase())) newErrors.cin_number = "Invalid CIN format";

      if (!form.pan_number?.trim()) newErrors.pan_number = "Required for India";
      else if (!PAN_REGEX.test(form.pan_number.toUpperCase())) newErrors.pan_number = "Invalid PAN format";
      else if (form.pan_number[3]?.toUpperCase() === "P") newErrors.pan_number = "Individual PAN not allowed — must be Company/Firm PAN";

      if (!form.gstin_number?.trim()) newErrors.gstin_number = "Required for India";
      else if (!GSTIN_REGEX.test(form.gstin_number.toUpperCase())) newErrors.gstin_number = "Invalid GSTIN format";

      if (!form.ifsc_code?.trim()) newErrors.ifsc_code = "Required for India";
      else if (!IFSC_REGEX.test(form.ifsc_code.toUpperCase())) newErrors.ifsc_code = "Invalid IFSC format";

      if (!form.account_type) newErrors.account_type = "Required for India";
      if (!form.registered_state) newErrors.registered_state = "Required for India";

      if (!files.registration && !files.pan_gstin) newErrors.documents = "COI and PAN/GSTIN documents are required";
    } else {
      if (!form.registration_number.trim()) newErrors.registration_number = "Required";
      if (!form.tax_id?.trim()) newErrors.tax_id = "Required";
      if (!form.tax_id_type) newErrors.tax_id_type = "Required";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    if (!validate()) {
      setSubmitError("Please fix the errors above before submitting.");
      return;
    }
    setIsSubmitting(true);
    try {
      const result = resubmitRunId
        ? await resubmitVendor(resubmitRunId, form, files, resubmitNotes || undefined)
        : await createSubmission(form, files);
      router.push(`/vendor/${result.run_id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Submission failed. Please try again.");
      setIsSubmitting(false);
    }
  };

  // Live client-side validation
  const cinValidation = validateCIN(form.cin_number || "");
  const panValidation = validatePAN(form.pan_number || "");
  const gstinValidation = validateGSTIN(form.gstin_number || "", form.pan_number || "");
  const ifscValidation = validateIFSC(form.ifsc_code || "", form.bank_name);

  // Document list for status pills
  const indiaDocStatus = [
    { key: "registration", label: "COI", has: !!files.registration },
    { key: "pan_gstin", label: "PAN / GSTIN", has: !!files.pan_gstin },
    { key: "bank", label: "Bank Letter", has: !!files.bank },
  ];
  const genericDocStatus = [
    { key: "registration", label: "Registration", has: !!files.registration },
    { key: "bank", label: "Bank Letter", has: !!files.bank },
    { key: "tax", label: "Tax Certificate", has: !!files.tax },
  ];

  if (isLoadingPrefill) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-6 h-6 text-violet-400 animate-spin" />
          <p className="text-slate-400 text-sm">Loading previous submission...</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">

      {/* Resubmit Banner */}
      {resubmitRunId && (
        <div className="card border-violet-500/30 bg-violet-500/8">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-violet-300 mb-1">Resubmission Mode</p>
              <p className="text-xs text-slate-400 leading-relaxed mb-3">
                This is a resubmission of <span className="font-mono text-violet-400">{resubmitRunId}</span>.
                Please fix the issues from your previous submission. All documents must be re-uploaded.
              </p>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  What did you fix? <span className="text-slate-600">(optional)</span>
                </label>
                <textarea
                  className="input-field text-xs resize-none"
                  rows={2}
                  placeholder="e.g. Re-scanned the COI at higher resolution, corrected GSTIN format..."
                  value={resubmitNotes}
                  onChange={(e) => setResubmitNotes(e.target.value)}
                />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Company Information */}
      <div className="card">
        <SectionHeader
          icon={Building2}
          title="Company Information"
          subtitle="Legal entity details as they appear on your registration documents"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <FormField label="Company Name" required error={errors.company_name}>
              <input
                type="text"
                className="input-field"
                placeholder="Infosys Limited"
                value={form.company_name}
                onChange={(e) => updateField("company_name", e.target.value)}
              />
            </FormField>
          </div>

          <div className="sm:col-span-2">
            <FormField label="Country of Incorporation" required error={errors.country}>
              <select
                className="input-field"
                value={form.country}
                onChange={(e) => updateField("country", e.target.value)}
              >
                <option value="">Select country...</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.name}</option>
                ))}
              </select>
            </FormField>
          </div>

          {isIndia ? (
            <>
              {/* India: CIN */}
              <div className="sm:col-span-2">
                <FormField
                  label="CIN — Corporate Identification Number"
                  required
                  error={errors.cin_number}
                  hint="Format: [L/U][NIC5][State2][Year4][Type3][Num6] — e.g. L85110KA1981PLC013115"
                >
                  <input
                    type="text"
                    className="input-field font-mono tracking-wider"
                    placeholder="L85110KA1981PLC013115"
                    value={form.cin_number || ""}
                    onChange={(e) => updateField("cin_number", e.target.value.toUpperCase())}
                    maxLength={21}
                  />
                  {cinValidation && !errors.cin_number && (
                    <ValidationBadge status={cinValidation.status} message={cinValidation.msg} />
                  )}
                </FormField>
              </div>

              {/* India: Registered State */}
              <FormField label="Registered State" required error={errors.registered_state}>
                <select
                  className="input-field"
                  value={form.registered_state || ""}
                  onChange={(e) => updateField("registered_state", e.target.value)}
                >
                  <option value="">Select state...</option>
                  {INDIA_STATES.map((s) => (
                    <option key={s.code} value={s.name}>
                      {s.name} ({s.gstCode})
                    </option>
                  ))}
                </select>
              </FormField>

              {/* Incorporation Date */}
              <FormField label="Date of Incorporation" required error={errors.incorporation_date}>
                <input
                  type="date"
                  className="input-field"
                  value={form.incorporation_date}
                  onChange={(e) => updateField("incorporation_date", e.target.value)}
                />
              </FormField>
            </>
          ) : (
            <>
              <FormField label="Registration Number" required error={errors.registration_number}>
                <input
                  type="text"
                  className="input-field"
                  placeholder="12345678"
                  value={form.registration_number}
                  onChange={(e) => updateField("registration_number", e.target.value)}
                />
              </FormField>
              <FormField label="Incorporation Date" required error={errors.incorporation_date}>
                <input
                  type="date"
                  className="input-field"
                  value={form.incorporation_date}
                  onChange={(e) => updateField("incorporation_date", e.target.value)}
                />
              </FormField>
            </>
          )}
        </div>
      </div>

      {/* Contact Information */}
      <div className="card">
        <SectionHeader
          icon={User}
          title="Contact Information"
          subtitle="Primary contact for this vendor account"
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <FormField label="Contact Name" required error={errors.contact_name}>
            <input
              type="text"
              className="input-field"
              placeholder="Jane Smith"
              value={form.contact_name}
              onChange={(e) => updateField("contact_name", e.target.value)}
            />
          </FormField>
          <FormField label="Contact Email" required error={errors.contact_email}>
            <input
              type="email"
              className="input-field"
              placeholder="jane@company.com"
              value={form.contact_email}
              onChange={(e) => updateField("contact_email", e.target.value)}
            />
          </FormField>
        </div>
      </div>

      {/* Tax Information */}
      {isIndia ? (
        <div className="card">
          <SectionHeader
            icon={ShieldCheck}
            title="PAN & GST Information"
            subtitle="Income tax and GST registration — validated against each other automatically"
            badge="India"
          />

          {/* India: PAN */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <FormField
                label="PAN — Permanent Account Number"
                required
                error={errors.pan_number}
                hint="10 characters: [5 letters][4 digits][1 letter] — 4th char must be C (Company) or F (Firm)"
              >
                <input
                  type="text"
                  className="input-field font-mono tracking-widest"
                  placeholder="AAACI1681G"
                  value={form.pan_number || ""}
                  onChange={(e) => updateField("pan_number", e.target.value.toUpperCase())}
                  maxLength={10}
                />
                {panValidation && !errors.pan_number && (
                  <ValidationBadge status={panValidation.status} message={panValidation.msg} />
                )}
              </FormField>
            </div>

            {/* India: GSTIN */}
            <div className="sm:col-span-2">
              <FormField
                label="GSTIN — GST Identification Number"
                required
                error={errors.gstin_number}
                hint="15 characters: [2-digit state code][PAN][entity][Z][checksum] — e.g. 29AAACI1681G1ZK"
              >
                <input
                  type="text"
                  className="input-field font-mono tracking-wider"
                  placeholder="29AAACI1681G1ZK"
                  value={form.gstin_number || ""}
                  onChange={(e) => updateField("gstin_number", e.target.value.toUpperCase())}
                  maxLength={15}
                />
                {gstinValidation && !errors.gstin_number && (
                  <ValidationBadge status={gstinValidation.status} message={gstinValidation.msg} />
                )}
              </FormField>
            </div>
          </div>

          {/* Cross-validation info */}
          <div className="mt-4 p-3 rounded-xl bg-blue-500/6 border border-blue-500/20">
            <div className="flex items-center gap-1.5 mb-2">
              <Info className="w-3.5 h-3.5 text-blue-400" />
              <p className="text-xs text-blue-400 font-medium">Cross-Validation Checks (automatic)</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1">
              {[
                "GSTIN embeds your PAN (chars 3–12)",
                "GSTIN state code matches registered state",
                "PAN 4th character must be C (Company) or F (Firm)",
                "IFSC prefix identifies the correct bank",
                "Documents cross-checked against form data",
                "Account type must be Current Account",
              ].map((check) => (
                <div key={check} className="flex items-center gap-1.5 text-xs text-slate-500">
                  <CheckCircle className="w-3 h-3 text-blue-400/60 flex-shrink-0" />
                  {check}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <SectionHeader
            icon={CreditCard}
            title="Tax Information"
            subtitle="Tax registration details — auto-filled based on country selection"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <FormField
              label="Tax ID"
              required
              error={errors.tax_id}
              hint={form.country ? COUNTRY_TAX_DEFAULTS[form.country]?.label ?? "Enter your tax ID" : "Select country first"}
            >
              <input
                type="text"
                className="input-field"
                placeholder="Enter tax ID"
                value={form.tax_id || ""}
                onChange={(e) => updateField("tax_id", e.target.value)}
              />
            </FormField>
            <FormField label="Tax ID Type" required error={errors.tax_id_type}>
              <select
                className="input-field"
                value={form.tax_id_type || ""}
                onChange={(e) => updateField("tax_id_type", e.target.value)}
              >
                <option value="">Select type...</option>
                {["VAT", "EIN", "GST", "GSTIN", "PAN", "ABN", "OTHER"].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </FormField>
          </div>
        </div>
      )}

      {/* Banking Information */}
      <div className="card">
        <SectionHeader
          icon={Landmark}
          title="Banking Information"
          subtitle={isIndia
            ? "Current Account required for Indian businesses. IFSC code will be validated against stated bank."
            : "Account name should match company name to avoid flags"
          }
          badge={isIndia ? "India" : undefined}
        />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="sm:col-span-2">
            <FormField
              label="Account Name"
              required
              error={errors.bank_account_name}
              hint="Must exactly match your company name as on your certificate"
            >
              <input
                type="text"
                className="input-field"
                placeholder="Infosys Limited"
                value={form.bank_account_name}
                onChange={(e) => updateField("bank_account_name", e.target.value)}
              />
            </FormField>
          </div>

          <div className="sm:col-span-2">
            <FormField
              label={isIndia ? "Account Number" : "Account Number / IBAN"}
              required
              error={errors.account_number}
            >
              <input
                type="text"
                className="input-field"
                placeholder={isIndia ? "000705008001" : "GB82WEST12345698765432"}
                value={form.account_number}
                onChange={(e) => updateField("account_number", e.target.value)}
              />
            </FormField>
          </div>

          <FormField label="Bank Name" required error={errors.bank_name}>
            <input
              type="text"
              className="input-field"
              placeholder={isIndia ? "HDFC Bank" : "Barclays Bank"}
              value={form.bank_name}
              onChange={(e) => updateField("bank_name", e.target.value)}
            />
          </FormField>

          <FormField label="Bank Country" required error={errors.bank_country}>
            <select
              className="input-field"
              value={form.bank_country}
              onChange={(e) => updateField("bank_country", e.target.value)}
            >
              <option value="">Select country...</option>
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>{c.name}</option>
              ))}
            </select>
          </FormField>

          {isIndia && (
            <>
              {/* India: IFSC */}
              <FormField
                label="IFSC Code"
                required
                error={errors.ifsc_code}
                hint="Format: [4-letter bank code][0][6-character branch] — e.g. HDFC0000007"
              >
                <input
                  type="text"
                  className="input-field font-mono tracking-widest"
                  placeholder="HDFC0000007"
                  value={form.ifsc_code || ""}
                  onChange={(e) => updateField("ifsc_code", e.target.value.toUpperCase())}
                  maxLength={11}
                />
                {ifscValidation && !errors.ifsc_code && (
                  <ValidationBadge status={ifscValidation.status} message={ifscValidation.msg} />
                )}
              </FormField>

              {/* India: Account Type */}
              <FormField label="Account Type" required error={errors.account_type}>
                <select
                  className="input-field"
                  value={form.account_type || ""}
                  onChange={(e) => updateField("account_type", e.target.value)}
                >
                  <option value="">Select type...</option>
                  <option value="Current Account">Current Account ✓ (required for business)</option>
                  <option value="Savings Account">Savings Account ⚠️ (flag — not for business)</option>
                  <option value="OD Account">OD / Overdraft Account</option>
                </select>
                {form.account_type === "Savings Account" && (
                  <ValidationBadge status="fail" message="Savings accounts cannot be used for commercial transactions above RBI limits. This will be flagged." />
                )}
                {form.account_type === "Current Account" && (
                  <ValidationBadge status="pass" message="Current Account — correct for Indian business vendors ✓" />
                )}
              </FormField>
            </>
          )}
        </div>
      </div>

      {/* Document Uploads */}
      <div className="card">
        <SectionHeader
          icon={FileText}
          title={isIndia ? "Required Documents — India" : "Supporting Documents"}
          subtitle={isIndia
            ? "Upload COI from MCA, PAN+GSTIN certificate, and cancelled cheque/bank letter"
            : "Upload PDF, JPG, or PNG — max 10MB each. AI will extract data automatically."
          }
          badge={isIndia ? "India" : undefined}
        />

        {isIndia ? (
          /* India Document Slots */
          <div className="space-y-4">
            {/* India info box */}
            <div className="flex items-start gap-3 p-3 rounded-xl bg-orange-500/8 border border-orange-500/20">
              <Info className="w-4 h-4 text-orange-400 flex-shrink-0 mt-0.5" />
              <div className="text-xs text-slate-400 leading-relaxed">
                <span className="text-orange-400 font-medium">India KYB Documents: </span>
                COI from MCA · PAN card from Income Tax Dept · GSTIN certificate from GST portal · Cancelled cheque or bank letter on bank letterhead
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <FileUploadZone
                label="Certificate of Incorporation (COI)"
                description="Issued by MCA / Registrar of Companies"
                file={files.registration}
                onFileChange={(f) => setFiles((prev) => ({ ...prev, registration: f }))}
                required
                badge="MCA"
              />
              <FileUploadZone
                label="PAN Card + GSTIN Certificate"
                description="Combined PAN + GST registration doc"
                file={files.pan_gstin}
                onFileChange={(f) => setFiles((prev) => ({ ...prev, pan_gstin: f }))}
                required
                badge="IT Dept / GSTN"
              />
              <FileUploadZone
                label="Cancelled Cheque / Bank Letter"
                description="On bank letterhead with IFSC & account details"
                file={files.bank}
                onFileChange={(f) => setFiles((prev) => ({ ...prev, bank: f }))}
                required
                badge="Bank"
              />
            </div>
          </div>
        ) : (
          /* Generic Document Slots */
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <FileUploadZone
              label="Registration Certificate"
              description="PDF, JPG, PNG up to 10MB"
              file={files.registration}
              onFileChange={(f) => setFiles((prev) => ({ ...prev, registration: f }))}
              required
            />
            <FileUploadZone
              label="Bank Letter / Voided Cheque"
              description="PDF, JPG, PNG up to 10MB"
              file={files.bank}
              onFileChange={(f) => setFiles((prev) => ({ ...prev, bank: f }))}
              required
            />
            <FileUploadZone
              label="Tax Certificate"
              description="PDF, JPG, PNG up to 10MB"
              file={files.tax}
              onFileChange={(f) => setFiles((prev) => ({ ...prev, tax: f }))}
              required
            />
          </div>
        )}

        {/* Document Status Pills */}
        <div className="mt-4 flex flex-wrap gap-2">
          {(isIndia ? indiaDocStatus : genericDocStatus).map(({ key, label, has }) => (
            <div
              key={key}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full
                ${has
                  ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-400"
                  : "bg-slate-800/60 border border-slate-700/50 text-slate-500"
                }`}
            >
              {has ? <CheckCircle className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Submit error */}
      {(submitError || errors.documents) && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          <p className="text-sm">{submitError || errors.documents}</p>
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting}
        className="w-full py-3.5 px-6 bg-violet-600 hover:bg-violet-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all duration-200 shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 flex items-center justify-center gap-2 text-sm"
      >
        {isSubmitting ? (
          <><Loader2 className="w-4 h-4 animate-spin" />{resubmitRunId ? "Resubmitting..." : "Submitting..."}</>
        ) : (
          <>{resubmitRunId ? "Resubmit for Validation" : "Submit for Validation"} <ChevronRight className="w-4 h-4" /></>
        )}
      </button>

      <p className="text-center text-xs text-slate-600">
        {isIndia
          ? "India: 3-layer validation — Format checks, OCR extraction, and cross-document consistency"
          : "Your submission will be validated automatically. You'll be redirected to a live pipeline view."
        }
      </p>
    </form>
  );
}
