import type { ClaimStatus, TimelineEvent } from "../api/types";

/** What a member sees for a claim's status -- plain language, no internal
 * workflow states like "pending_adjuster_review" or "under_review".
 */
export function memberStatusLabel(status: ClaimStatus): string {
  switch (status) {
    case "submitted":
      return "Received";
    case "under_review":
    case "pending_adjuster_review":
      return "Under review";
    case "pending_documents":
      return "Waiting on you";
    case "approved":
    case "paid":
      return "Approved";
    case "denied":
      return "Denied";
    case "appealed":
      return "Under appeal";
    case "closed":
      return "Closed";
    default:
      return status;
  }
}

// Internal AI-pipeline events (extraction, retrieval, rule resolution,
// guardrail checks, etc.) are deliberately not shown to members -- only
// the milestones that are actually about *their* claim's progress.
const MEMBER_VISIBLE_EVENT_TYPES = new Set([
  "claim_created",
  "document_uploaded",
  "paused_for_human_review",
  "information_requested",
  "human_decision_recorded",
  "auto_processed",
]);

export interface MemberTimelineStep {
  key: number;
  label: string;
  description: string | null;
  timestamp: string;
}

const EVENT_LABELS: Record<string, string> = {
  claim_created: "Claim submitted",
  document_uploaded: "Document received",
  paused_for_human_review: "Sent to an adjuster for review",
  information_requested: "We need more information from you",
  human_decision_recorded: "Decision made",
  auto_processed: "Decision made",
};

export function toMemberTimeline(events: TimelineEvent[]): MemberTimelineStep[] {
  return events
    .filter((event) => MEMBER_VISIBLE_EVENT_TYPES.has(event.event_type))
    .map((event) => ({
      key: event.event_id,
      label: EVENT_LABELS[event.event_type] ?? event.event_type,
      description: event.event_type === "information_requested" ? event.description : null,
      timestamp: event.created_at,
    }));
}
