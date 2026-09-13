import { useNavigate } from "react-router-dom";

import type { AdjusterQueueItem } from "../../api/types";
import { formatCurrency, formatDate, titleCase } from "../../lib/format";
import { StatusBadge } from "../ui/Badge";
import { EmptyState } from "../ui/Feedback";

export function QueueTable({ claims }: { claims: AdjusterQueueItem[] }) {
  const navigate = useNavigate();

  if (claims.length === 0) {
    return <EmptyState message="No claims waiting in this queue." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead>
          <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-4">Claim</th>
            <th className="py-2 pr-4">Member</th>
            <th className="py-2 pr-4">Type</th>
            <th className="py-2 pr-4">Billed</th>
            <th className="py-2 pr-4">Date of service</th>
            <th className="py-2 pr-4">Submitted</th>
            <th className="py-2 pr-4">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {claims.map((claim) => (
            <tr
              key={claim.claim_id}
              onClick={() => navigate(`/claims/${claim.claim_id}`)}
              className="cursor-pointer hover:bg-slate-50"
            >
              <td className="py-3 pr-4 font-medium text-slate-900">{claim.claim_number}</td>
              <td className="py-3 pr-4 text-slate-700">{claim.member_name}</td>
              <td className="py-3 pr-4 text-slate-700">{titleCase(claim.claim_type)}</td>
              <td className="py-3 pr-4 text-slate-700">{formatCurrency(claim.billed_amount)}</td>
              <td className="py-3 pr-4 text-slate-700">{formatDate(claim.date_of_service)}</td>
              <td className="py-3 pr-4 text-slate-700">{formatDate(claim.submitted_at)}</td>
              <td className="py-3 pr-4">
                <StatusBadge status={claim.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
