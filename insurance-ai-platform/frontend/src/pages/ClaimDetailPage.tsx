import { Link, useParams } from "react-router-dom";

import { useClaim, useDocuments, useReviewPacket, useSubmitClaim } from "../api/queries";
import { AIRecommendationPanel } from "../components/claim-detail/AIRecommendationPanel";
import { AuditTimeline } from "../components/claim-detail/AuditTimeline";
import { ClaimHeader } from "../components/claim-detail/ClaimHeader";
import { DecisionActions } from "../components/claim-detail/DecisionActions";
import { DocumentViewer } from "../components/claim-detail/DocumentViewer";
import { FraudIndicators } from "../components/claim-detail/FraudIndicators";
import { PolicyCitations } from "../components/claim-detail/PolicyCitations";
import { ErrorState, Spinner } from "../components/ui/Feedback";

export function ClaimDetailPage() {
  const { claimId } = useParams<{ claimId: string }>();
  if (!claimId) return null;

  const claimQuery = useClaim(claimId);
  const packetQuery = useReviewPacket(claimId);
  const documentsQuery = useDocuments(claimId);
  const submitMutation = useSubmitClaim(claimId);

  if (claimQuery.isLoading || packetQuery.isLoading || documentsQuery.isLoading) {
    return <Spinner label="Loading claim…" />;
  }

  if (claimQuery.isError || packetQuery.isError || documentsQuery.isError || !claimQuery.data || !packetQuery.data) {
    return <ErrorState message="Could not load this claim." />;
  }

  const claim = claimQuery.data;
  const packet = packetQuery.data;
  const documents = documentsQuery.data ?? [];

  return (
    <div className="space-y-6">
      <Link to="/" className="text-sm font-medium text-emerald-700 hover:underline">
        ← Back to queue
      </Link>

      <ClaimHeader
        claim={claim}
        packet={packet}
        onSubmit={() => submitMutation.mutate()}
        isSubmitting={submitMutation.isPending}
      />

      {submitMutation.isError && <ErrorState message="Could not submit this claim for AI review." />}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <DocumentViewer claimId={claimId} documents={documents} />
          <AIRecommendationPanel packet={packet} />
          <PolicyCitations citations={packet.policy_citations} />
        </div>

        <div className="space-y-6">
          <DecisionActions claim={claim} packet={packet} />
          <FraudIndicators packet={packet} />
        </div>
      </div>

      <AuditTimeline events={packet.audit_history} />
    </div>
  );
}
