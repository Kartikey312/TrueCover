import type { ClaimReviewPacket } from "../../api/types";
import { formatConfidence, titleCase } from "../../lib/format";
import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import { EmptyState } from "../ui/Feedback";

const RECOMMENDATION_TONE: Record<string, "success" | "danger" | "warning" | "info"> = {
  approve: "success",
  deny: "danger",
  flag_for_fraud: "danger",
  request_more_info: "warning",
  escalate: "info",
};

export function AIRecommendationPanel({ packet }: { packet: ClaimReviewPacket }) {
  if (!packet.recommendation_type) {
    return (
      <Card title="AI recommendation">
        <EmptyState message="Not submitted for AI review yet." />
      </Card>
    );
  }

  return (
    <Card title="AI recommendation">
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Badge tone={RECOMMENDATION_TONE[packet.recommendation_type] ?? "neutral"}>
            {titleCase(packet.recommendation_type)}
          </Badge>
          <span className="text-sm text-slate-500">
            Confidence: <span className="font-medium text-slate-700">{formatConfidence(packet.confidence_score)}</span>
          </span>
        </div>

        {packet.reasoning && <p className="text-sm text-slate-700">{packet.reasoning}</p>}

        <div>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Guardrail checks ({packet.guardrail_checks.filter((c) => c.passed).length}/{packet.guardrail_checks.length}{" "}
            passed)
          </h3>
          <ul className="space-y-1">
            {packet.guardrail_checks.map((check) => (
              <li key={check.name} className="flex items-start gap-2 text-sm">
                <span className={check.passed ? "text-emerald-600" : "text-red-600"}>{check.passed ? "✓" : "✕"}</span>
                <div>
                  <span className="font-medium text-slate-800">{titleCase(check.name)}</span>
                  {!check.passed && check.reason && <span className="text-slate-500"> — {check.reason}</span>}
                </div>
              </li>
            ))}
          </ul>
        </div>

        {packet.guardrail_reason && (
          <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-200">
            {packet.guardrail_reason}
          </p>
        )}
      </div>
    </Card>
  );
}
