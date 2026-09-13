import { Link } from "react-router-dom";

import { useMemberClaims } from "../api/queries";
import { ClaimsList } from "../components/claims/ClaimsList";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ErrorState, Spinner } from "../components/ui/Feedback";
import { useMemberIdentity } from "../context/MemberContext";

export function MyClaimsPage() {
  const { memberId } = useMemberIdentity();
  const { data: claims, isLoading, isError } = useMemberClaims(memberId);

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
        {!memberId && <ErrorState message="Select who you are (top right) to see your claims." />}
        {memberId && isLoading && <Spinner label="Loading your claims…" />}
        {memberId && isError && <ErrorState message="Could not load your claims." />}
        {memberId && claims && <ClaimsList claims={claims} />}
      </Card>
    </div>
  );
}
