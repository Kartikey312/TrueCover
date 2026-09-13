import type { TimelineEvent } from "../../api/types";
import { toMemberTimeline } from "../../lib/memberView";
import { formatDateTime } from "../../lib/format";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

export function ClaimProgress({ events }: { events: TimelineEvent[] }) {
  const steps = toMemberTimeline(events);

  return (
    <Card title="Claim progress">
      {steps.length === 0 ? (
        <EmptyState message="No updates yet." />
      ) : (
        <ol className="space-y-4">
          {steps.map((step) => (
            <li key={step.key} className="relative pl-5">
              <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-blue-400" />
              <div className="text-sm font-medium text-slate-900">{step.label}</div>
              {step.description && <p className="mt-0.5 text-sm text-slate-600">{step.description}</p>}
              <div className="text-xs text-slate-400">{formatDateTime(step.timestamp)}</div>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
