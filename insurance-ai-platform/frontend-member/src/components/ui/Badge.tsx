import type { ReactNode } from "react";

type Tone = "neutral" | "success" | "danger" | "warning" | "info";

const TONE_CLASSES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-500/20",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  danger: "bg-red-50 text-red-700 ring-red-600/20",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/20",
  info: "bg-blue-50 text-blue-700 ring-blue-600/20",
};

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

const STATUS_TONE: Record<string, Tone> = {
  Received: "info",
  "Under review": "warning",
  "Waiting on you": "warning",
  Approved: "success",
  Denied: "danger",
  "Under appeal": "warning",
  Closed: "neutral",
};

export function MemberStatusBadge({ label }: { label: string }) {
  return <Badge tone={STATUS_TONE[label] ?? "neutral"}>{label}</Badge>;
}
