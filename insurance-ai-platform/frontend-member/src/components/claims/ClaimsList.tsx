import { useNavigate } from "react-router-dom";

import type { ClaimRead } from "../../api/types";
import { formatCurrency, formatDate, titleCase } from "../../lib/format";
import { memberStatusLabel } from "../../lib/memberView";
import { MemberStatusBadge } from "../ui/Badge";
import { EmptyState } from "../ui/Feedback";

export function ClaimsList({ claims }: { claims: ClaimRead[] }) {
  const navigate = useNavigate();

  if (claims.length === 0) {
    return <EmptyState message="You haven't filed any claims yet." />;
  }

  return (
    <ul className="divide-y divide-slate-100">
      {claims.map((claim) => (
        <li
          key={claim.claim_id}
          onClick={() => navigate(`/claims/${claim.claim_id}`)}
          className="flex cursor-pointer items-center justify-between py-3 hover:bg-slate-50"
        >
          <div>
            <div className="font-medium text-slate-900">{claim.claim_number}</div>
            <div className="text-sm text-slate-500">
              {titleCase(claim.claim_type)} · {formatDate(claim.date_of_service)} ·{" "}
              {formatCurrency(claim.billed_amount)}
            </div>
          </div>
          <MemberStatusBadge label={memberStatusLabel(claim.status)} />
        </li>
      ))}
    </ul>
  );
}
