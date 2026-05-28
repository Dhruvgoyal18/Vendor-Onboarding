"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getSubmission, getVersions, subscribeToRunEvents } from "@/lib/api";
import { VendorDetail, VendorVersion, SSEUpdate, SubmissionStatus, PipelineStage, PipelineStageKey, STAGE_LABELS } from "@/lib/types";
import PipelineTracker from "@/components/PipelineTracker";
import { formatDistanceToNow, format } from "date-fns";
import {
  CheckCircle, XCircle, AlertTriangle, Clock, Loader2, ArrowLeft,
  Mail, RefreshCw, GitBranch, FileText, ChevronDown, ChevronUp,
  AlertCircle, Info, FileX, ExternalLink, ArrowRight, Building2,
} from "lucide-react";

// ─── Status Config ────────────────────────────────────────────────────────────────
const STATUS_CONFIG: Record<SubmissionStatus, {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
  bg: string;
  border: string;
  text: string;
  iconColor: string;
  spin?: boolean;
}> = {
  processing: {
    icon: Loader2, title: "Your Application is Being Reviewed",
    subtitle: "Our AI is validating your documents and cross-checking all details.",
    bg: "bg-blue-500/10", border: "border-blue-500/30", text: "text-blue-300",
    iconColor: "text-blue-400", spin: true,
  },
  pending: {
    icon: AlertTriangle, title: "Action Required",
    subtitle: "We need some information or corrected documents from you.",
    bg: "bg-amber-500/10", border: "border-amber-500/30", text: "text-amber-300",
    iconColor: "text-amber-400",
  },
  approved: {
    icon: CheckCircle, title: "Congratulations! Application Approved",
    subtitle: "Your vendor onboarding is complete. You will be contacted with next steps.",
    bg: "bg-emerald-500/10", border: "border-emerald-500/30", text: "text-emerald-300",
    iconColor: "text-emerald-400",
  },
  rejected: {
    icon: XCircle, title: "Application Not Approved",
    subtitle: "Unfortunately we are unable to onboard your company at this time.",
    bg: "bg-red-500/10", border: "border-red-500/30", text: "text-red-300",
    iconColor: "text-red-400",
  },
  error: {
    icon: AlertCircle, title: "Processing Error",
    subtitle: "Something went wrong. Please contact our support team.",
    bg: "bg-rose-500/10", border: "border-rose-500/30", text: "text-rose-300",
    iconColor: "text-rose-400",
  },
};

// ─── Email Type Labels ────────────────────────────────────────────────────────────
const EMAIL_TYPE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  ocr_failure: { label: "Document Issue", color: "text-amber-400", bg: "bg-amber-500/10 border-amber-500/30" },
  pending_request: { label: "Action Required", color: "text-orange-400", bg: "bg-orange-500/10 border-orange-500/30" },
  rejection_neutral: { label: "Application Update", color: "text-red-400", bg: "bg-red-500/10 border-red-500/30" },
  approval: { label: "Approved", color: "text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/30" },
};

// ─── Issue Extraction ─────────────────────────────────────────────────────────────
function extractIssues(vendor: VendorDetail): { critical: string[]; warnings: string[]; info: string[] } {
  const critical: string[] = [];
  const warnings: string[] = [];
  const info: string[] = [];

  // OCR failures
  vendor.documents.forEach((doc) => {
    if (doc.ocr_status === "failed") {
      const label = {
        coi: "Certificate of Incorporation",
        registration: "Registration Certificate",
        pan_gstin: "PAN Card & GSTIN Certificate",
        tax_cert: "Tax Certificate",
        bank_letter: "Bank Letter / Cancelled Cheque",
        bank: "Bank Letter / Cancelled Cheque",
      }[doc.document_type] || doc.document_type.replace(/_/g, " ");
      critical.push(`${label}: Could not extract text — please re-scan at higher resolution (300 DPI+)`);
    } else if (doc.ocr_status === "partial") {
      const label = doc.document_type.replace(/_/g, " ");
      warnings.push(`${label}: Only partial information was extracted — ensure the document is clear and unobscured`);
    }
  });

  // Validation failures
  vendor.validation_results.forEach((r) => {
    if (["fail", "mismatch", "missing"].includes(r.status) && r.detail) {
      const friendlyDetail = r.detail
        .replace(/^(Field|Required field)\s+'?/, "")
        .replace(/_/g, " ")
        .replace(/\bfield\b/gi, "")
        .trim();
      if (r.status === "missing") {
        critical.push(`Missing: ${friendlyDetail}`);
      } else {
        critical.push(friendlyDetail);
      }
    } else if (r.status === "warning" && r.detail) {
      warnings.push(r.detail);
    }
  });

  return { critical: [...new Set(critical)], warnings: [...new Set(warnings)], info };
}

// ─── Version Timeline ─────────────────────────────────────────────────────────────
function VersionTimeline({ versions, currentRunId }: { versions: VendorVersion[]; currentRunId: string }) {
  if (versions.length <= 1) return null;

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="w-4 h-4 text-violet-400" />
        <h3 className="text-sm font-semibold text-white">Submission History</h3>
        <span className="ml-auto text-xs text-slate-500">{versions.length} version{versions.length !== 1 ? "s" : ""}</span>
      </div>
      <div className="space-y-3">
        {versions.map((v, i) => {
          const isCurrent = v.run_id === currentRunId;
          const statusColor = {
            approved: "text-emerald-400",
            rejected: "text-red-400",
            pending: "text-amber-400",
            processing: "text-blue-400",
            error: "text-rose-400",
          }[v.status] || "text-slate-400";

          return (
            <div key={v.run_id} className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${isCurrent ? "bg-violet-500/8 border-violet-500/25" : "bg-slate-800/30 border-slate-700/40"}`}>
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${isCurrent ? "bg-violet-500/20 text-violet-400" : "bg-slate-700/60 text-slate-500"}`}>
                v{v.version_number}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <span className={`text-xs font-medium ${statusColor}`}>
                    {v.status.charAt(0).toUpperCase() + v.status.slice(1)}
                  </span>
                  <span className="text-xs text-slate-600">
                    {format(new Date(v.created_at), "MMM d, yyyy")}
                  </span>
                </div>
                {v.resubmission_notes && (
                  <p className="text-xs text-slate-400 mt-1 leading-relaxed">{v.resubmission_notes}</p>
                )}
                {!isCurrent && (
                  <button
                    onClick={() => window.location.href = `/vendor/${v.run_id}`}
                    className="text-xs text-violet-400 hover:text-violet-300 mt-1 transition-colors"
                  >
                    View this version →
                  </button>
                )}
                {isCurrent && <span className="text-xs text-violet-400 mt-1 block">Current</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Email Panel ──────────────────────────────────────────────────────────────────
function EmailPanel({ vendor }: { vendor: VendorDetail }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (vendor.email_logs.length === 0) return null;

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Mail className="w-4 h-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-white">Emails Sent To You</h3>
        <span className="ml-auto text-xs text-slate-500">{vendor.email_logs.length} email{vendor.email_logs.length !== 1 ? "s" : ""}</span>
      </div>
      <div className="space-y-2">
        {vendor.email_logs.map((email) => {
          const typeInfo = EMAIL_TYPE_LABELS[email.email_type || ""] || {
            label: email.email_type || "Notification",
            color: "text-slate-400",
            bg: "bg-slate-800/40 border-slate-700/40",
          };
          const isExpanded = expandedId === email.id;

          return (
            <div key={email.id} className={`rounded-xl border ${typeInfo.bg} overflow-hidden`}>
              <button
                onClick={() => setExpandedId(isExpanded ? null : email.id)}
                className="w-full flex items-center gap-3 p-3 text-left"
              >
                <Mail className={`w-4 h-4 ${typeInfo.color} flex-shrink-0`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-300 truncate">{email.subject}</p>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {format(new Date(email.sent_at), "MMM d, yyyy 'at' h:mm a")}
                  </p>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${typeInfo.bg} ${typeInfo.color} flex-shrink-0`}>
                  {typeInfo.label}
                </span>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-500 flex-shrink-0" /> : <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />}
              </button>
              {isExpanded && email.body && (
                <div className="px-3 pb-3 border-t border-slate-700/30">
                  <pre className="text-xs text-slate-400 mt-2 leading-relaxed whitespace-pre-wrap font-sans">
                    {email.body}
                  </pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── OCR Document Status ──────────────────────────────────────────────────────────
function DocumentStatus({ vendor }: { vendor: VendorDetail }) {
  if (vendor.documents.length === 0) return null;

  const DOC_LABELS: Record<string, string> = {
    coi: "Certificate of Incorporation",
    registration: "Registration Certificate",
    pan_gstin: "PAN Card & GSTIN Certificate",
    tax_cert: "Tax Certificate",
    bank_letter: "Bank Letter / Cancelled Cheque",
    bank: "Bank Letter",
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <FileText className="w-4 h-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-white">Document Status</h3>
      </div>
      <div className="space-y-2">
        {vendor.documents.map((doc) => {
          const label = DOC_LABELS[doc.document_type] || doc.document_type.replace(/_/g, " ");
          const statusConfig = {
            success: { icon: CheckCircle, color: "text-emerald-400", bg: "bg-emerald-500/5 border-emerald-500/20", label: "Extracted Successfully" },
            partial: { icon: AlertTriangle, color: "text-amber-400", bg: "bg-amber-500/5 border-amber-500/20", label: "Partially Extracted" },
            failed: { icon: FileX, color: "text-red-400", bg: "bg-red-500/5 border-red-500/20", label: "Could Not Extract" },
            unknown: { icon: Clock, color: "text-slate-500", bg: "bg-slate-800/30 border-slate-700/40", label: "Processing..." },
          }[doc.ocr_status] || { icon: Clock, color: "text-slate-500", bg: "bg-slate-800/30 border-slate-700/40", label: "Pending" };

          const StatusIcon = statusConfig.icon;

          return (
            <div key={doc.id} className={`flex items-start gap-3 p-3 rounded-xl border ${statusConfig.bg}`}>
              <StatusIcon className={`w-4 h-4 ${statusConfig.color} flex-shrink-0 mt-0.5`} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-slate-300">{label}</p>
                <p className={`text-xs ${statusConfig.color} mt-0.5`}>{statusConfig.label}</p>
                {doc.ocr_issues && doc.ocr_issues.length > 0 && (
                  <ul className="mt-1 space-y-0.5">
                    {doc.ocr_issues.map((issue, i) => (
                      <li key={i} className="text-xs text-slate-500 leading-relaxed">• {issue}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────────
export default function VendorPortalPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;

  const [vendor, setVendor] = useState<VendorDetail | null>(null);
  const [versions, setVersions] = useState<VendorVersion[]>([]);
  const [status, setStatus] = useState<SubmissionStatus>("processing");
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [currentStage, setCurrentStage] = useState<PipelineStageKey | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [data, vers] = await Promise.all([
          getSubmission(runId),
          getVersions(runId).catch(() => [] as VendorVersion[]),
        ]);
        setVendor(data);
        setStatus(data.status);
        setStages(data.pipeline_stages);
        setCurrentStage(data.current_stage);
        setVersions(vers);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Application not found");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [runId]);

  // SSE for live updates
  useEffect(() => {
    if (!runId) return;
    const unsub = subscribeToRunEvents(runId, (update: SSEUpdate) => {
      setStatus(update.status);
      setStages(update.stages);
      setCurrentStage(update.current_stage);
      if (["approved", "rejected", "pending", "error"].includes(update.status)) {
        getSubmission(runId).then((data) => {
          setVendor(data); setStatus(data.status);
          setStages(data.pipeline_stages); setCurrentStage(data.current_stage);
        });
        getVersions(runId).catch(() => []).then(setVersions);
      }
    });
    return unsub;
  }, [runId]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-8 h-8 text-violet-400 animate-spin" />
          <p className="text-slate-400 text-sm">Loading your application...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full card border-red-500/20 text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <h2 className="text-white font-semibold mb-2">Application Not Found</h2>
          <p className="text-slate-400 text-sm mb-6">{error}</p>
          <button
            onClick={() => router.push("/vendor")}
            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.processing;
  const Icon = config.icon;
  const { critical, warnings } = vendor ? extractIssues(vendor) : { critical: [], warnings: [] };
  const canResubmit = ["pending", "rejected"].includes(status);
  const versionNum = vendor?.version_number || 1;

  return (
    <div className="min-h-screen py-8 px-4">
      <div className="max-w-2xl mx-auto">
        {/* Back */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Building2 className="w-5 h-5 text-violet-400" />
              <h1 className="text-xl font-bold text-white">{vendor?.company_name}</h1>
              {versionNum > 1 && (
                <span className="text-xs px-1.5 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-400">
                  v{versionNum}
                </span>
              )}
            </div>
            <p className="text-xs text-slate-600 font-mono">{runId}</p>
            {vendor?.created_at && (
              <p className="text-xs text-slate-600 mt-0.5">
                Submitted {formatDistanceToNow(new Date(vendor.created_at), { addSuffix: true })}
              </p>
            )}
          </div>
          <button
            onClick={() => getSubmission(runId).then((d) => { setVendor(d); setStatus(d.status); })}
            className="p-2 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-500 hover:text-slate-300 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        <div className="space-y-4">
          {/* Status Banner */}
          <div className={`card border ${config.bg} ${config.border}`}>
            <div className="flex items-start gap-3">
              <Icon className={`w-6 h-6 mt-0.5 flex-shrink-0 ${config.iconColor} ${config.spin ? "animate-spin" : ""}`} />
              <div className="flex-1">
                <h2 className={`font-semibold ${config.text} mb-1`}>{config.title}</h2>
                <p className="text-sm text-slate-400 leading-relaxed">{config.subtitle}</p>
                {vendor?.risk_level && status === "rejected" && (
                  <p className="text-xs text-slate-500 mt-2">
                    Please contact our procurement team if you have questions.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Live Pipeline — shown while processing */}
          {status === "processing" && stages.length > 0 && (
            <div className="card">
              <div className="flex items-center gap-2 mb-4">
                <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                <h3 className="text-sm font-semibold text-white">Validation Progress</h3>
                <span className="ml-auto text-xs text-blue-400 animate-pulse">Live</span>
              </div>
              <PipelineTracker stages={stages} currentStage={currentStage} />
            </div>
          )}

          {/* Issues to Fix */}
          {critical.length > 0 && (
            <div className="card border-red-500/20">
              <div className="flex items-center gap-2 mb-3">
                <AlertCircle className="w-4 h-4 text-red-400" />
                <h3 className="text-sm font-semibold text-white">Issues to Resolve</h3>
                <span className="ml-auto text-xs px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-400 border border-red-500/30">
                  {critical.length} issue{critical.length !== 1 ? "s" : ""}
                </span>
              </div>
              <ul className="space-y-2">
                {critical.map((issue, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400 leading-relaxed">
                    <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0 mt-0.5" />
                    {issue}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="card border-amber-500/20">
              <div className="flex items-center gap-2 mb-3">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-white">Warnings</h3>
              </div>
              <ul className="space-y-2">
                {warnings.map((w, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs text-slate-400 leading-relaxed">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Document Status */}
          {vendor && <DocumentStatus vendor={vendor} />}

          {/* Emails */}
          {vendor && <EmailPanel vendor={vendor} />}

          {/* Version Timeline */}
          <VersionTimeline versions={versions} currentRunId={runId} />

          {/* Resubmit CTA */}
          {canResubmit && (
            <div className="card border-violet-500/20 bg-violet-500/5 text-center">
              <Info className="w-5 h-5 text-violet-400 mx-auto mb-2" />
              <h3 className="text-sm font-semibold text-white mb-1">Ready to Resubmit?</h3>
              <p className="text-xs text-slate-400 mb-4 leading-relaxed">
                Fix the issues listed above and resubmit your application. Your previous submission will be preserved as v{versionNum}.
              </p>
              <a
                href={`/submit?resubmit=${runId}`}
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-xl transition-all shadow-lg shadow-violet-500/20"
              >
                Resubmit Application (v{versionNum + 1})
                <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
