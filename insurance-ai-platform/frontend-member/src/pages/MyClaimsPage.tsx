import { Link } from "react-router-dom";

import { useMemberClaims } from "../api/queries";
import { ClaimsList } from "../components/claims/ClaimsList";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorState, Spinner } from "../components/ui/Feedback";
import { useMemberAuth } from "../context/MemberContext";

export function MyClaimsPage() {
  const { member } = useMemberAuth();
  const { data: claims, isLoading, isError } = useMemberClaims(member!.member_id);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">My claims</h1>
          <p className="text-sm text-slate-500">Track the status of claims you've filed.</p>
        </div>
        <Link to="/claims/new">
          <Button variant="primary">File a new claim</Button>
        </Link>
      </div>

      <Card>
        {isLoading && <Spinner label="Loading your claims…" />}
        {isError && <ErrorState message="Could not load your claims." />}
        {claims && <ClaimsList claims={claims} />}
      </Card>
    </div>
  );
}
