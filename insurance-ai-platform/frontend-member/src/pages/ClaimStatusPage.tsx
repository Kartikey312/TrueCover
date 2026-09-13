import { Link, useParams } from "react-router-dom";

import { useClaim, useClaimDocuments, useClaimTimeline } from "../api/queries";
import { ClaimDocumentsCard } from "../components/claims/ClaimDocumentsCard";
import { ClaimProgress } from "../components/claims/ClaimProgress";
import { ClaimStatusCard } from "../components/claims/ClaimStatusCard";
import { ErrorState, Spinner } from "../components/ui/Feedback";

export function ClaimStatusPage() {
  const { claimId } = useParams<{ claimId: string }>();
  if (!claimId) return null;

  const claimQuery = useClaim(claimId);
  const documentsQuery = useClaimDocuments(claimId);
  const timelineQuery = useClaimTimeline(claimId);

  if (claimQuery.isLoading) {
    return <Spinner label="Loading your claim…" />;
  }
  if (claimQuery.isError || !claimQuery.data) {
    return <ErrorState message="Could not load this claim." />;
  }

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm font-medium text-blue-700 hover:underline">
        ← Back to my claims
      </Link>

      <ClaimStatusCard claim={claimQuery.data} />

      {documentsQuery.data && <ClaimDocumentsCard documents={documentsQuery.data} />}
      {timelineQuery.data && <ClaimProgress events={timelineQuery.data} />}
    </div>
  );
}
