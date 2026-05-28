"use client";

import { PipelineStage, PipelineStageKey, StageStatus, STAGE_LABELS } from "@/lib/types";
import { CheckCircle, Circle, Clock, AlertCircle, Loader2, ChevronRight } from "lucide-react";

interface PipelineTrackerProps {
  stages: PipelineStage[];
  currentStage: PipelineStageKey | null;
}

const ORDERED_STAGES: PipelineStageKey[] = [
  "intake",
  "extract_fields",
  "format_check",
  "external_verification",
  "extract_docs",
  "cross_doc_check",
  "merge",
  "check_completeness",
  "check_consistency",
  "check_credibility",
  "decide",
  "output",
  "done",
];

function StageIcon({ status }: { status: StageStatus }) {
  switch (status) {
    case "completed":
      return <CheckCircle className="w-5 h-5 text-emerald-400" />;
    case "running":
      return <Loader2 className="w-5 h-5 text-blue-400 animate-spin" />;
    case "failed":
      return <AlertCircle className="w-5 h-5 text-red-400" />;
    case "skipped":
      return <Circle className="w-5 h-5 text-slate-600" />;
    default:
      return <Clock className="w-5 h-5 text-slate-600" />;
  }
}

function getStageColor(status: StageStatus): string {
  switch (status) {
    case "completed":
      return "border-emerald-500/50 bg-emerald-500/5";
    case "running":
      return "border-blue-500/70 bg-blue-500/10 shadow-lg shadow-blue-500/10";
    case "failed":
      return "border-red-500/50 bg-red-500/5";
    default:
      return "border-slate-700/50 bg-slate-800/30";
  }
}

function getConnectorColor(status: StageStatus): string {
  return status === "completed" ? "bg-emerald-500/50" : "bg-slate-700/50";
}

export default function PipelineTracker({
  stages,
  currentStage,
}: PipelineTrackerProps) {
  // Build a map for quick lookup
  const stageMap = new Map<string, PipelineStage>();
  stages.forEach((s) => stageMap.set(s.stage, s));

  // Display stages (exclude "done" as a separate item - it's part of output)
  const displayStages = ORDERED_STAGES.filter((s) => s !== "done");

  return (
    <div className="space-y-0">
      {displayStages.map((stageKey, index) => {
        const stage = stageMap.get(stageKey);
        const status: StageStatus = stage?.status ?? "pending";
        const isLast = index === displayStages.length - 1;

        return (
          <div key={stageKey} className="flex gap-3">
            {/* Connector line */}
            <div className="flex flex-col items-center">
              <div
                className={`w-10 h-10 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all duration-500
                  ${getStageColor(status)}`}
              >
                <StageIcon status={status} />
              </div>
              {!isLast && (
                <div
                  className={`w-0.5 flex-1 min-h-[20px] my-1 transition-all duration-500 ${getConnectorColor(status)}`}
                />
              )}
            </div>

            {/* Stage content */}
            <div className={`flex-1 pb-${isLast ? "0" : "4"} min-w-0`}>
              <div
                className={`p-3 rounded-xl border transition-all duration-500
                  ${status === "running" ? "border-blue-500/50 bg-blue-500/5" : "border-transparent bg-transparent"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-sm font-medium transition-colors duration-300 ${
                      status === "completed"
                        ? "text-emerald-300"
                        : status === "running"
                        ? "text-blue-300"
                        : status === "failed"
                        ? "text-red-300"
                        : "text-slate-500"
                    }`}
                  >
                    {STAGE_LABELS[stageKey]}
                  </span>
                  {status === "running" && (
                    <span className="text-xs text-blue-400/70 animate-pulse">
                      Running...
                    </span>
                  )}
                  {status === "completed" && stage?.completed_at && (
                    <span className="text-xs text-slate-600">
                      ✓ Done
                    </span>
                  )}
                </div>
                {stage?.message && status !== "pending" && (
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                    {stage.message}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
