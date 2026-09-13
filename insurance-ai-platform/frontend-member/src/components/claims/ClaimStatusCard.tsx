import type { ClaimRead } from "../../api/types";
import { formatCurrency, formatDate, formatDateTime, titleCase } from "../../lib/format";
import { memberStatusLabel } from "../../lib/memberView";
import { MemberStatusBadge } from "../ui/Badge";

export function ClaimStatusCard({ claim }: { claim: ClaimRead }) {
  const statusLabel = memberStatusLabel(claim.status);

  return (
    <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <h1 className="text-lg font-semibold text-slate-900">{claim.claim_number}</h1>
        <MemberStatusBadge label={statusLabel} />
      </div>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-slate-500">Claim type</dt>
          <dd className="font-medium text-slate-900">{titleCase(claim.claim_type)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Date of service</dt>
          <dd className="font-medium text-slate-900">{formatDate(claim.date_of_service)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Billed amount</dt>
          <dd className="font-medium text-slate-900">{formatCurrency(claim.billed_amount)}</dd>
        </div>
        {claim.approved_amount !== null && (
          <div>
            <dt className="text-slate-500">Approved amount</dt>
            <dd className="font-medium text-slate-900">{formatCurrency(claim.approved_amount)}</dd>
          </div>
        )}
      </dl>

      {claim.final_decision !== "pending" && (
        <div className="rounded-md bg-slate-50 px-3 py-2 text-sm text-slate-700 ring-1 ring-inset ring-slate-200">
          <span className="font-medium">{statusLabel}.</span> {claim.final_decision_reason} —{" "}
          {formatDateTime(claim.final_decision_at)}
        </div>
      )}

      {claim.status === "pending_documents" && (
        <div className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-200">
          We need more information from you to keep processing this claim — see the note below.
        </div>
      )}
    </div>
  );
}
