import type { PolicyCitation } from "../../api/types";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

export function PolicyCitations({ citations }: { citations: PolicyCitation[] }) {
  return (
    <Card title="Policy citations">
      {citations.length === 0 ? (
        <EmptyState message="No policy context was retrieved for this claim." />
      ) : (
        <ul className="space-y-3">
          {citations.map((citation, index) => (
            <li key={index} className="rounded-md border border-slate-200 p-3 text-sm">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {citation.source.replace(/_/g, " ")}
              </div>
              {citation.text && <p className="text-slate-700">{citation.text}</p>}
              {citation.network_status && (
                <p className="mt-1 text-slate-500">
                  Network status: <span className="font-medium text-slate-700">{citation.network_status}</span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
