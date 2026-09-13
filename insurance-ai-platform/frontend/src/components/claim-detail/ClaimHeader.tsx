import type { ClaimRead, ClaimReviewPacket } from "../../api/types";
import { formatCurrency, formatDate, formatDateTime, titleCase } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";
import { Button } from "../ui/Button";

export function ClaimHeader({
  claim,
  packet,
  onSubmit,
  isSubmitting,
}: {
  claim: ClaimRead;
  packet: ClaimReviewPacket;
  onSubmit: () => void;
  isSubmitting: boolean;
}) {
  const notYetSubmitted = claim.current_graph_thread_id === null;

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-lg font-semibold text-slate-900">{claim.claim_number}</h1>
            <StatusBadge status={claim.status} />
          </div>
          <p className="mt-1 text-sm text-slate-500">
            {packet.member_name} · Policy {packet.policy_number}
            {packet.provider_name && <> · {packet.provider_name}</>}
          </p>
        </div>

        {notYetSubmitted && (
          <Button variant="primary" onClick={onSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Submitting…" : "Submit for AI review"}
          </Button>
        )}
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 border-t border-slate-100 pt-3 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">Claim type</dt>
          <dd className="font-medium text-slate-900">{titleCase(packet.claim_type)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Billed amount</dt>
          <dd className="font-medium text-slate-900">{formatCurrency(packet.billed_amount)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Date of service</dt>
          <dd className="font-medium text-slate-900">{formatDate(packet.date_of_service)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Approved amount</dt>
          <dd className="font-medium text-slate-900">{formatCurrency(claim.approved_amount)}</dd>
        </div>
      </dl>

      {claim.final_decision !== "pending" && (
        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200">
          <span className="font-medium">Final decision: {titleCase(claim.final_decision)}.</span>{" "}
          {claim.final_decision_reason} — {formatDateTime(claim.final_decision_at)}
        </div>
      )}
    </div>
  );
}
