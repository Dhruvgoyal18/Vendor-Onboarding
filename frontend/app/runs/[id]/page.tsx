"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { getSubmission, getStages, getVersions, subscribeToRunEvents } from "@/lib/api";
import {
  VendorDetail, PipelineStage, PipelineStageKey, SubmissionStatus,
  SSEUpdate, STAGE_LABELS, ValidationResult, VendorVersion,
} from "@/lib/types";
import PipelineTracker from "@/components/PipelineTracker";
import StatusBadge from "@/components/StatusBadge";
import { format, formatDistanceToNow } from "date-fns";
import {
  CheckCircle, AlertTriangle, XCircle, Clock, Loader2, ArrowLeft,
  Building2, Shield, FileText, ChevronDown, ChevronUp, Copy, Mail,
  RefreshCw, GitBranch, BarChart3, FileX, AlertCircle, ShieldAlert,
} from "lucide-react";

// ─── Score Calculation ─────────────────────────────────────────────────────────────
function computeScore(results: ValidationResult[]): number {
  const active = results.filter((r) => !["skipped", "error"].includes(r.status));
  if (active.length === 0) return -1;
  let points = 0;
  for (const r of active) {
    if (["pass", "match", "completed"].includes(r.status)) points += 1;
    else if (["warning", "partial_match"].includes(r.status)) points += 0.5;
  }
  return Math.round((points / active.length) * 100);
}

function computeOverallScore(
  byCategory: Record<string, ValidationResult[]>
): number {
  const weights: Record<string, number> = {
    format_check: 0.25, completeness: 0.25, cross_doc_check: 0.20,
    consistency: 0.20, credibility: 0.10,
  };
  let totalWeight = 0;
  let weightedSum = 0;
  for (const [cat, weight] of Object.entries(weights)) {
    const score = computeScore(byCategory[cat] ?? []);
    if (score >= 0) { weightedSum += score * weight; totalWeight += weight; }
  }
  return totalWeight > 0 ? Math.round(weightedSum / totalWeight) : -1;
}

// ─── Score Ring ────────────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 52 }: { score: number; size?: number }) {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = score >= 0 ? circumference * (1 - score / 100) : circumference;
  const color = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : score >= 0 ? "#ef4444" : "#475569";

  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="#1e293b" strokeWidth={6} />
      <circle
        cx={size / 2} cy={size / 2} r={radius} fill="none"
        stroke={color} strokeWidth={6} strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={strokeDashoffset}
        style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
    </svg>
  );
}

// ─── Category Score Card ───────────────────────────────────────────────────────────
const CATEGORY_META: Record<string, {
  label: string; icon: React.ComponentType<{ className?: string }>;
  description: string;
}> = {
  format_check: { label: "Identity & Format", icon: Shield, description: "PAN, GSTIN, CIN, IFSC format validation" },
  completeness: { label: "Completeness", icon: FileText, description: "Required fields and documents" },
  cross_doc_check: { label: "Cross-Document", icon: FileText, description: "Document ↔ form data matching" },
  consistency: { label: "Consistency", icon: CheckCircle, description: "Form vs extracted document data" },
  credibility: { label: "Risk & Credibility", icon: AlertTriangle, description: "Fraud signals and risk assessment" },
};

function CategoryScoreCard({
  category, results,
}: {
  category: string; results: ValidationResult[];
}) {
  const meta = CATEGORY_META[category];
  if (!meta || results.length === 0) return null;

  const score = computeScore(results);
  const passCount = results.filter((r) => ["pass", "match"].includes(r.status)).length;
  const failCount = results.filter((r) => ["fail", "mismatch", "missing"].includes(r.status)).length;
  const warnCount = results.filter((r) => ["warning", "partial_match"].includes(r.status)).length;
  const Icon = meta.icon;

  const scoreColor = score >= 80 ? "text-emerald-400" : score >= 60 ? "text-amber-400" : score >= 0 ? "text-red-400" : "text-slate-500";
  const scoreBg = score >= 80 ? "bg-emerald-500/10" : score >= 60 ? "bg-amber-500/10" : score >= 0 ? "bg-red-500/10" : "bg-slate-800/40";

  return (
    <div className={`card p-4 ${scoreBg} border-slate-700/50`}>
      <div className="flex items-center gap-3">
        <div className="relative flex items-center justify-center">
          <ScoreRing score={score} size={52} />
          <div className="absolute inset-0 flex items-center justify-center">
            <span className={`text-sm font-bold ${scoreColor}`}>
              {score >= 0 ? `${score}%` : "N/A"}
            </span>
          </div>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-semibold text-white">{meta.label}</p>
          <p className="text-[10px] text-slate-500 mt-0.5 leading-tight">{meta.description}</p>
          <div className="flex items-center gap-2 mt-1.5">
            {passCount > 0 && <span className="text-[10px] text-emerald-400">{passCount}✓</span>}
            {warnCount > 0 && <span className="text-[10px] text-amber-400">{warnCount}⚠</span>}
            {failCount > 0 && <span className="text-[10px] text-red-400">{failCount}✗</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Validation Section ────────────────────────────────────────────────────────────
function ValidationSection({
  title, results, defaultOpen = false,
}: {
  title: string; results: ValidationResult[]; defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pass": case "match": case "completed":
        return <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
      case "fail": case "mismatch": case "missing":
        return <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />;
      case "warning": case "partial_match":
        return <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />;
      default:
        return <Clock className="w-4 h-4 text-slate-500 flex-shrink-0" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "pass": case "match": return "border-emerald-500/20 bg-emerald-500/5";
      case "fail": case "mismatch": case "missing": return "border-red-500/20 bg-red-500/5";
      case "warning": case "partial_match": return "border-amber-500/20 bg-amber-500/5";
      default: return "border-slate-700/40 bg-slate-800/20";
    }
  };

  const passCount = results.filter((r) => ["pass", "match"].includes(r.status)).length;
  const failCount = results.filter((r) => ["fail", "mismatch", "missing"].includes(r.status)).length;
  const warnCount = results.filter((r) => ["warning", "partial_match"].includes(r.status)).length;
  const score = computeScore(results);

  return (
    <div className="card">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-white">{title}</span>
          <div className="flex items-center gap-1.5">
            {passCount > 0 && <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400">{passCount} pass</span>}
            {warnCount > 0 && <span className="text-xs px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-400">{warnCount} warn</span>}
            {failCount > 0 && <span className="text-xs px-1.5 py-0.5 rounded-full bg-red-500/15 text-red-400">{failCount} fail</span>}
            {score >= 0 && (
              <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                score >= 80 ? "bg-emerald-500/15 text-emerald-400" : score >= 60 ? "bg-amber-500/15 text-amber-400" : "bg-red-500/15 text-red-400"
              }`}>{score}%</span>
            )}
          </div>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
      </button>

      {open && (
        <div className="mt-4 space-y-2">
          {results.map((r) => (
            <div key={r.id} className={`flex items-start gap-2.5 p-3 rounded-lg border ${getStatusColor(r.status)}`}>
              {getStatusIcon(r.status)}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-medium text-slate-300">{r.check_name.replace(/_/g, " ")}</p>
                {r.detail && <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{r.detail}</p>}
                {r.confidence != null && (
                  <div className="mt-1.5 flex items-center gap-2">
                    <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                      <div className="h-full bg-violet-500/60 rounded-full" style={{ width: `${r.confidence * 100}%` }} />
                    </div>
                    <span className="text-xs text-slate-600">{Math.round(r.confidence * 100)}%</span>
                  </div>
                )}
              </div>
            </div>
          ))}
          {results.length === 0 && <p className="text-xs text-slate-600 text-center py-4">No checks</p>}
        </div>
      )}
    </div>
  );
}

// ─── Decision Banner ──────────────────────────────────────────────────────────────
function DecisionBanner({ status, summary, riskLevel }: {
  status: SubmissionStatus; summary: string | null; riskLevel: string | null;
}) {
  const configs: Record<SubmissionStatus, {
    icon: React.ComponentType<{ className?: string }>;
    title: string; bg: string; text: string; iconColor: string; glow?: string; spin?: boolean;
  }> = {
    approved: { icon: CheckCircle, title: "Vendor Approved", bg: "bg-emerald-500/10 border-emerald-500/30", text: "text-emerald-300", iconColor: "text-emerald-400", glow: "glow-emerald" },
    pending: { icon: Clock, title: "Action Required", bg: "bg-amber-500/10 border-amber-500/30", text: "text-amber-300", iconColor: "text-amber-400" },
    rejected: { icon: XCircle, title: "Submission Rejected", bg: "bg-red-500/10 border-red-500/30", text: "text-red-300", iconColor: "text-red-400", glow: "glow-red" },
    processing: { icon: Loader2, title: "Processing...", bg: "bg-blue-500/10 border-blue-500/30", text: "text-blue-300", iconColor: "text-blue-400", spin: true },
    error: { icon: AlertTriangle, title: "Processing Error", bg: "bg-rose-500/10 border-rose-500/30", text: "text-rose-300", iconColor: "text-rose-400" },
  };
  const config = configs[status] ?? configs.processing;
  const Icon = config.icon;

  return (
    <div className={`card border ${config.bg} ${config.glow ?? ""}`}>
      <div className="flex items-start gap-3">
        <Icon className={`w-6 h-6 mt-0.5 flex-shrink-0 ${config.iconColor} ${config.spin ? "animate-spin" : ""}`} />
        <div className="flex-1 min-w-0">
          <h3 className={`font-semibold text-base ${config.text} mb-1`}>{config.title}</h3>
          {summary
            ? <p className="text-sm text-slate-400 leading-relaxed whitespace-pre-line">{summary}</p>
            : <p className="text-sm text-slate-500">{status === "processing" ? "Running validation pipeline..." : "No summary available"}</p>
          }
          {riskLevel && status !== "processing" && (
            <div className="mt-3 inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-slate-800/60 border border-slate-700/50 text-slate-400">
              <Shield className="w-3 h-3" />
              Risk level: <span className={riskLevel === "high" ? "text-red-400" : riskLevel === "medium" ? "text-amber-400" : "text-emerald-400"}>{riskLevel}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Email Log ────────────────────────────────────────────────────────────────────
function AdminEmailLog({ vendor }: { vendor: VendorDetail }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  if (vendor.email_logs.length === 0) return null;

  const TYPE_CONFIG: Record<string, { label: string; color: string }> = {
    ocr_failure: { label: "OCR Failure", color: "text-amber-400" },
    pending_request: { label: "Pending Request", color: "text-orange-400" },
    rejection_neutral: { label: "Rejection", color: "text-red-400" },
    approval: { label: "Approval", color: "text-emerald-400" },
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Mail className="w-4 h-4 text-slate-400" />
        <h3 className="text-sm font-semibold text-white">Email Log</h3>
        <span className="ml-auto text-xs text-slate-500">{vendor.email_logs.length} sent</span>
      </div>
      <div className="space-y-2">
        {vendor.email_logs.map((email) => {
          const typeInfo = TYPE_CONFIG[email.email_type || ""] || { label: email.email_type || "Email", color: "text-slate-400" };
          const isOpen = expandedId === email.id;
          return (
            <div key={email.id} className="rounded-xl border border-slate-700/50 bg-slate-800/30 overflow-hidden">
              <button
                onClick={() => setExpandedId(isOpen ? null : email.id)}
                className="w-full flex items-center gap-3 p-3 text-left"
              >
                <Mail className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-slate-300 truncate">{email.subject}</p>
                  <p className="text-xs text-slate-600">
                    To: {email.recipient} · {format(new Date(email.sent_at), "MMM d, h:mm a")}
                  </p>
                </div>
                <span className={`text-[10px] font-medium ${typeInfo.color} flex-shrink-0`}>{typeInfo.label}</span>
                {email.success
                  ? <CheckCircle className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                  : <XCircle className="w-3.5 h-3.5 text-red-400 flex-shrink-0" />
                }
                {isOpen ? <ChevronUp className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" /> : <ChevronDown className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />}
              </button>
              {isOpen && email.body && (
                <div className="px-3 pb-3 border-t border-slate-700/30">
                  <pre className="text-xs text-slate-400 mt-2 whitespace-pre-wrap font-sans leading-relaxed">{email.body}</pre>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Version History ──────────────────────────────────────────────────────────────
function VersionHistory({ versions, currentRunId }: { versions: VendorVersion[]; currentRunId: string }) {
  if (versions.length <= 1) return null;
  const router = useRouter();

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="w-4 h-4 text-violet-400" />
        <h3 className="text-sm font-semibold text-white">Version History</h3>
        <span className="ml-auto text-xs text-slate-500">{versions.length} versions</span>
      </div>
      <div className="space-y-2">
        {versions.map((v) => {
          const isCurrent = v.run_id === currentRunId;
          const statusColor = { approved: "text-emerald-400", rejected: "text-red-400", pending: "text-amber-400", processing: "text-blue-400", error: "text-rose-400" }[v.status] || "text-slate-400";
          return (
            <div
              key={v.run_id}
              onClick={() => !isCurrent && router.push(`/runs/${v.run_id}`)}
              className={`flex items-start gap-3 p-3 rounded-xl border transition-all ${isCurrent ? "bg-violet-500/8 border-violet-500/25" : "bg-slate-800/30 border-slate-700/40 cursor-pointer hover:border-slate-600"}`}
            >
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5 ${isCurrent ? "bg-violet-500/20 text-violet-400" : "bg-slate-700/60 text-slate-500"}`}>
                v{v.version_number}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-xs font-medium ${statusColor}`}>{v.status.charAt(0).toUpperCase() + v.status.slice(1)}</span>
                  <span className="text-xs text-slate-600">{format(new Date(v.created_at), "MMM d, yyyy")}</span>
                </div>
                {v.resubmission_notes && <p className="text-xs text-slate-500 mt-1 leading-relaxed">{v.resubmission_notes}</p>}
                {v.decision_summary && <p className="text-xs text-slate-600 mt-1 truncate">{v.decision_summary}</p>}
                {isCurrent && <span className="text-[10px] text-violet-400 mt-1 block">Current</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Override Modal ───────────────────────────────────────────────────────────────
function OverrideModal({
  runId, onClose, onSuccess,
}: {
  runId: string; onClose: () => void; onSuccess: (status: string) => void;
}) {
  const [decision, setDecision] = useState<"approved" | "rejected">("approved");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!reason.trim()) { setError("Reason is required"); return; }
    setLoading(true);
    setError(null);
    try {
      const { apiRequest } = await import("@/lib/api");
      await apiRequest(`/api/submissions/${runId}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, reason: reason.trim() }),
        auth: "admin",
      });
      onSuccess(decision);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Override failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md bg-slate-900 border border-slate-700/60 rounded-2xl shadow-2xl p-6">
        <div className="flex items-center gap-3 mb-5">
          <ShieldAlert className="w-5 h-5 text-amber-400" />
          <h2 className="text-base font-semibold text-white">Admin Override</h2>
          <button onClick={onClose} className="ml-auto text-slate-500 hover:text-slate-300 text-sm">✕</button>
        </div>
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-slate-400 mb-2 block">Decision</label>
            <div className="grid grid-cols-2 gap-2">
              {(["approved", "rejected"] as const).map((d) => (
                <button
                  key={d}
                  onClick={() => setDecision(d)}
                  className={`py-2.5 rounded-xl text-sm font-medium border transition-all ${
                    decision === d
                      ? d === "approved"
                        ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                        : "bg-red-500/20 border-red-500/50 text-red-300"
                      : "bg-slate-800/50 border-slate-700/50 text-slate-400 hover:border-slate-600"
                  }`}
                >
                  {d === "approved" ? "✓ Approve" : "✗ Reject"}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs font-medium text-slate-400 mb-2 block">
              Reason <span className="text-red-400">*</span>
            </label>
            <textarea
              className="w-full bg-slate-800/60 border border-slate-700/50 rounded-xl px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 resize-none"
              rows={3}
              placeholder="Explain the reason for this override..."
              value={reason}
              onChange={(e) => { setReason(e.target.value); setError(null); }}
            />
            {error && <p className="text-xs text-red-400 mt-1">{error}</p>}
          </div>
          <div className="flex gap-3 pt-1">
            <button onClick={onClose} className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-sm transition-all">
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={loading}
              className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all flex items-center justify-center gap-2 ${
                decision === "approved"
                  ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                  : "bg-red-600 hover:bg-red-500 text-white"
              } disabled:opacity-50`}
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? "Overriding..." : `Override → ${decision.charAt(0).toUpperCase() + decision.slice(1)}`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Run Page ────────────────────────────────────────────────────────────────
export default function RunPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.id as string;

  const [vendor, setVendor] = useState<VendorDetail | null>(null);
  const [versions, setVersions] = useState<VendorVersion[]>([]);
  const [stages, setStages] = useState<PipelineStage[]>([]);
  const [status, setStatus] = useState<SubmissionStatus>("processing");
  const [currentStage, setCurrentStage] = useState<PipelineStageKey | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [riskLevel, setRiskLevel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showOverride, setShowOverride] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [data, vers] = await Promise.all([
          getSubmission(runId),
          getVersions(runId).catch(() => [] as VendorVersion[]),
        ]);
        setVendor(data);
        setStages(data.pipeline_stages);
        setStatus(data.status);
        setCurrentStage(data.current_stage);
        setSummary(data.decision_summary);
        setRiskLevel(data.risk_level);
        setVersions(vers);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load run");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    let stopPolling: (() => void) | null = null;
    const unsubscribe = subscribeToRunEvents(runId, (update: SSEUpdate) => {
      setStatus(update.status);
      setCurrentStage(update.current_stage);
      setStages(update.stages);
      if (update.decision_summary) setSummary(update.decision_summary);
      if (update.risk_level) setRiskLevel(update.risk_level);
      if (["approved", "rejected", "pending", "error"].includes(update.status)) {
        Promise.all([
          getSubmission(runId),
          getVersions(runId).catch(() => [] as VendorVersion[]),
        ]).then(([data, vers]) => {
          setVendor(data); setStages(data.pipeline_stages); setVersions(vers);
        });
      }
    }, () => {
      if (!stopPolling) stopPolling = startPolling();
    });
    return () => { unsubscribe(); stopPolling?.(); };
  }, [runId]);

  const startPolling = useCallback(() => {
    const interval = setInterval(async () => {
      try {
        const data = await getStages(runId);
        setStatus(data.status as SubmissionStatus);
        setCurrentStage(data.current_stage as PipelineStageKey | null);
        setStages(data.stages.map((s) => ({
          stage: s.stage as PipelineStageKey,
          status: s.status as any,
          message: s.message,
          started_at: s.started_at,
          completed_at: s.completed_at,
        })));
        if (["approved", "rejected", "pending", "error"].includes(data.status)) {
          clearInterval(interval);
          getSubmission(runId).then((detail) => {
            setVendor(detail); setSummary(detail.decision_summary); setRiskLevel(detail.risk_level);
          });
        }
      } catch {}
    }, 2000);
    return () => clearInterval(interval);
  }, [runId]);

  const copyRunId = () => { navigator.clipboard.writeText(runId); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4"><Loader2 className="w-8 h-8 text-violet-400 animate-spin" /><p className="text-slate-400 text-sm">Loading...</p></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="max-w-md w-full card border-red-500/20 text-center">
          <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-4" />
          <h2 className="text-white font-semibold mb-2">Run Not Found</h2>
          <p className="text-slate-400 text-sm mb-6">{error}</p>
          <button onClick={() => router.push("/dashboard")} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-slate-300 text-sm rounded-lg transition-colors">Dashboard</button>
        </div>
      </div>
    );
  }

  // Group checks by category
  const byCategory: Record<string, ValidationResult[]> = {};
  for (const r of vendor?.validation_results ?? []) {
    if (!byCategory[r.category]) byCategory[r.category] = [];
    byCategory[r.category].push(r);
  }

  const overallScore = computeOverallScore(byCategory);
  const categories = ["format_check", "completeness", "cross_doc_check", "consistency", "credibility"];
  const versionNum = vendor?.version_number || 1;

  return (
    <div className="min-h-screen py-8 px-4">
      {showOverride && (
        <OverrideModal
          runId={runId}
          onClose={() => setShowOverride(false)}
          onSuccess={(newStatus) => {
            setStatus(newStatus as SubmissionStatus);
            getSubmission(runId).then((d) => { setVendor(d); setSummary(d.decision_summary); setRiskLevel(d.risk_level); });
          }}
        />
      )}
      <div className="max-w-6xl mx-auto">
        {/* Back */}
        <button onClick={() => router.push("/dashboard")} className="flex items-center gap-2 text-slate-500 hover:text-slate-300 text-sm mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" />Back to Dashboard
        </button>

        {/* Admin badge */}
        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400 text-xs font-medium mb-4">
          <BarChart3 className="w-3 h-3" />Admin View
        </div>

        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center shadow-lg shadow-purple-500/25 flex-shrink-0">
              <Building2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-2xl font-bold text-white">{vendor?.company_name ?? "Loading..."}</h1>
                {versionNum > 1 && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-violet-500/15 border border-violet-500/30 text-violet-400">v{versionNum}</span>
                )}
              </div>
              <div className="flex items-center gap-2 mt-1">
                <button onClick={copyRunId} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-400 transition-colors">
                  <span className="font-mono">{runId}</span>
                  <Copy className="w-3 h-3" />
                  {copied && <span className="text-emerald-400">Copied!</span>}
                </button>
                {vendor?.is_duplicate && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400">⚠ Duplicate</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status={status} size="lg" />
            {status !== "processing" && (
              <button
                onClick={() => setShowOverride(true)}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-sm transition-all"
                title="Override decision"
              >
                <ShieldAlert className="w-4 h-4" />
                Override
              </button>
            )}
            <button
              onClick={() => Promise.all([getSubmission(runId), getVersions(runId).catch(() => [])]).then(([d, v]) => { setVendor(d); setStages(d.pipeline_stages); setVersions(v); setStatus(d.status); setSummary(d.decision_summary); setRiskLevel(d.risk_level); })}
              className="p-2 rounded-lg bg-slate-800/60 border border-slate-700/50 text-slate-500 hover:text-slate-300 transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Overall Score + Category Score Cards */}
        {overallScore >= 0 && (
          <div className="mb-6">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex items-center gap-2">
                <div className="relative">
                  <ScoreRing score={overallScore} size={44} />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-xs font-bold ${overallScore >= 80 ? "text-emerald-400" : overallScore >= 60 ? "text-amber-400" : "text-red-400"}`}>
                      {overallScore}%
                    </span>
                  </div>
                </div>
                <div>
                  <p className="text-xs font-semibold text-white">Overall Score</p>
                  <p className="text-[10px] text-slate-500">Weighted across all categories</p>
                </div>
              </div>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
              {categories.map((cat) => (
                <CategoryScoreCard key={cat} category={cat} results={byCategory[cat] ?? []} />
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
          {/* Left — Pipeline + Vendor Info */}
          <div className="lg:col-span-2 space-y-4">
            <div className="card">
              <div className="flex items-center gap-2 mb-5">
                <div className="w-7 h-7 rounded-lg bg-violet-500/15 flex items-center justify-center">
                  <Loader2 className={`w-3.5 h-3.5 text-violet-400 ${status === "processing" ? "animate-spin" : ""}`} />
                </div>
                <h2 className="text-sm font-semibold text-white">Live Pipeline</h2>
                {status === "processing" && <span className="ml-auto text-xs text-blue-400 animate-pulse">Live</span>}
              </div>
              <PipelineTracker stages={stages} currentStage={currentStage} />
            </div>

            {vendor && (
              <div className="card">
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">Submission Details</h3>
                <div className="space-y-3">
                  {[
                    { label: "Country", value: vendor.country },
                    { label: "Contact", value: vendor.contact_name },
                    { label: "Email", value: vendor.contact_email },
                    { label: "Tax ID", value: vendor.tax_id },
                    { label: "Bank", value: vendor.bank_account_name },
                    { label: "Bank Country", value: vendor.bank_country },
                  ].map(({ label, value }) =>
                    value ? (
                      <div key={label} className="flex justify-between gap-3 text-xs">
                        <span className="text-slate-500">{label}</span>
                        <span className="text-slate-300 text-right font-medium truncate max-w-[60%]">{value}</span>
                      </div>
                    ) : null
                  )}
                </div>

                {/* Documents with OCR status */}
                {vendor.documents.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-slate-700/50">
                    <p className="text-xs text-slate-500 mb-3">Documents</p>
                    <div className="space-y-2">
                      {vendor.documents.map((doc) => {
                        const ocrConfig = {
                          success: { icon: CheckCircle, color: "text-emerald-400", label: "Extracted" },
                          partial: { icon: AlertTriangle, color: "text-amber-400", label: "Partial" },
                          failed: { icon: FileX, color: "text-red-400", label: "Failed" },
                          unknown: { icon: Clock, color: "text-slate-500", label: "Pending" },
                        }[doc.ocr_status] || { icon: Clock, color: "text-slate-500", label: "Pending" };
                        const OcrIcon = ocrConfig.icon;
                        return (
                          <div key={doc.id} className="flex items-center gap-2 text-xs">
                            <FileText className="w-3.5 h-3.5 text-slate-500 flex-shrink-0" />
                            <span className="text-slate-400 capitalize flex-1">{doc.document_type.replace(/_/g, " ")}</span>
                            <div className="flex items-center gap-1">
                              <OcrIcon className={`w-3 h-3 ${ocrConfig.color}`} />
                              <span className={`text-[10px] ${ocrConfig.color}`}>{ocrConfig.label}</span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Version History (left panel) */}
            <VersionHistory versions={versions} currentRunId={runId} />
          </div>

          {/* Right — Decision + Checks + Emails */}
          <div className="lg:col-span-3 space-y-4">
            <DecisionBanner status={status} summary={summary} riskLevel={riskLevel} />

            {categories.map((cat) => {
              const results = byCategory[cat] ?? [];
              if (results.length === 0) return null;
              const labels: Record<string, string> = {
                format_check: "Identity & Format Checks",
                completeness: "Completeness Checks",
                cross_doc_check: "Cross-Document Checks",
                consistency: "Consistency Analysis",
                credibility: "Credibility & Fraud Analysis",
              };
              return (
                <ValidationSection
                  key={cat}
                  title={labels[cat] || cat.replace(/_/g, " ")}
                  results={results}
                  defaultOpen={results.some((r) => ["fail", "mismatch", "missing"].includes(r.status))}
                />
              );
            })}

            {vendor?.is_duplicate && vendor.duplicate_of_run_id && (
              <div className="card border-amber-500/30 bg-amber-500/5">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm font-medium text-amber-300">Duplicate Submission Detected</p>
                    <p className="text-xs text-slate-400 mt-1">
                      Previously submitted as{" "}
                      <button onClick={() => router.push(`/runs/${vendor.duplicate_of_run_id}`)} className="text-amber-400 hover:underline font-mono">
                        {vendor.duplicate_of_run_id}
                      </button>
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* Email Log */}
            {vendor && <AdminEmailLog vendor={vendor} />}

            {/* Vendor Portal Link */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-800/30 border border-slate-700/40">
              <Mail className="w-4 h-4 text-slate-500 flex-shrink-0" />
              <span className="text-xs text-slate-500 flex-1">Vendor portal link:</span>
              <a
                href={`/vendor/${runId}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-violet-400 hover:text-violet-300 transition-colors font-mono"
              >
                /vendor/{runId}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
