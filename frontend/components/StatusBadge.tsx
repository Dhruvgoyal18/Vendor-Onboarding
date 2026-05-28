"use client";

import { SubmissionStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: SubmissionStatus | string;
  size?: "sm" | "md" | "lg";
}

const STATUS_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; dot: string; glow: string }
> = {
  processing: {
    label: "Processing",
    bg: "bg-blue-500/15 border border-blue-500/30",
    text: "text-blue-300",
    dot: "bg-blue-400",
    glow: "shadow-blue-500/20",
  },
  pending: {
    label: "Pending",
    bg: "bg-amber-500/15 border border-amber-500/30",
    text: "text-amber-300",
    dot: "bg-amber-400",
    glow: "shadow-amber-500/20",
  },
  approved: {
    label: "Approved",
    bg: "bg-emerald-500/15 border border-emerald-500/30",
    text: "text-emerald-300",
    dot: "bg-emerald-400",
    glow: "shadow-emerald-500/20",
  },
  rejected: {
    label: "Rejected",
    bg: "bg-red-500/15 border border-red-500/30",
    text: "text-red-300",
    dot: "bg-red-400",
    glow: "shadow-red-500/20",
  },
  error: {
    label: "Error",
    bg: "bg-rose-500/15 border border-rose-500/30",
    text: "text-rose-300",
    dot: "bg-rose-400",
    glow: "shadow-rose-500/20",
  },
};

const SIZE_CLASSES = {
  sm: "text-xs px-2 py-0.5",
  md: "text-xs px-2.5 py-1",
  lg: "text-sm px-3 py-1.5",
};

export default function StatusBadge({
  status,
  size = "md",
}: StatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.processing;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-medium
        ${config.bg} ${config.text} ${SIZE_CLASSES[size]}`}
    >
      <span
        className={`inline-block w-1.5 h-1.5 rounded-full ${config.dot}
          ${status === "processing" ? "animate-pulse" : ""}`}
      />
      {config.label}
    </span>
  );
}
