import type { TimelineEvent } from "../../api/types";
import { formatDateTime, titleCase } from "../../lib/format";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

const ACTOR_LABEL: Record<string, string> = {
  user: "Adjuster",
  system: "System",
  ai_agent: "AI pipeline",
};

export function AuditTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <Card title="Audit timeline">
      {events.length === 0 ? (
        <EmptyState message="No audit events recorded yet." />
      ) : (
        <ol className="space-y-4">
          {events.map((event) => (
            <li key={event.event_id} className="relative pl-5">
              <span className="absolute left-0 top-1.5 h-2 w-2 rounded-full bg-slate-300" />
              <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
                <span className="font-medium text-slate-900">{titleCase(event.event_type)}</span>
                <span className="text-xs text-slate-400">{ACTOR_LABEL[event.actor_type] ?? event.actor_type}</span>
                <span className="text-xs text-slate-400">· {formatDateTime(event.created_at)}</span>
              </div>
              {event.description && <p className="mt-0.5 text-sm text-slate-600">{event.description}</p>}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
