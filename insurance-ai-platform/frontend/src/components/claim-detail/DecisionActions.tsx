import { useState } from "react";

import { useDecision, useRequestInfo } from "../../api/queries";
import { ApiError } from "../../api/client";
import type { ClaimRead, ClaimReviewPacket } from "../../api/types";
import { formatCurrency, titleCase } from "../../lib/format";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { ErrorState } from "../ui/Feedback";
import { Modal } from "../ui/Modal";

type PendingDecision = "approved" | "denied";

const AI_RECOMMENDATION_TO_DECISION: Record<string, PendingDecision | undefined> = {
  approve: "approved",
  deny: "denied",
};

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export function DecisionActions({ claim, packet }: { claim: ClaimRead; packet: ClaimReviewPacket }) {
  const decisionMutation = useDecision(claim.claim_id);
  const requestInfoMutation = useRequestInfo(claim.claim_id);

  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null);
  const [approvedAmount, setApprovedAmount] = useState("");
  const [reason, setReason] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(newIdempotencyKey);

  const [requestInfoOpen, setRequestInfoOpen] = useState(false);
  const [message, setMessage] = useState("");

  const canAct = claim.current_graph_thread_id !== null && claim.final_decision === "pending";
  const aiRecommendedDecision = packet.recommendation_type
    ? AI_RECOMMENDATION_TO_DECISION[packet.recommendation_type]
    : undefined;

  if (!canAct) {
    return null;
  }

  function openDecisionModal(decision: PendingDecision) {
    setPendingDecision(decision);
    setApprovedAmount(decision === "approved" ? claim.billed_amount ?? "" : "");
    setReason("");
    setIdempotencyKey(newIdempotencyKey());
    decisionMutation.reset();
  }

  function closeDecisionModal() {
    setPendingDecision(null);
  }

  function submitDecision() {
    if (!pendingDecision) return;
    decisionMutation.mutate(
      {
        final_decision: pendingDecision,
        approved_amount: pendingDecision === "approved" ? approvedAmount || null : null,
        reason,
        idempotency_key: idempotencyKey,
      },
      { onSuccess: () => setPendingDecision(null) },
    );
  }

  function submitRequestInfo() {
    requestInfoMutation.mutate(
      { message },
      {
        onSuccess: () => {
          setRequestInfoOpen(false);
          setMessage("");
        },
      },
    );
  }

  const isOverride = pendingDecision !== null && aiRecommendedDecision !== undefined && aiRecommendedDecision !== pendingDecision;

  return (
    <Card title="Decision">
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => openDecisionModal("approved")}>
          Approve
        </Button>
        <Button variant="danger" onClick={() => openDecisionModal("denied")}>
          Deny
        </Button>
        <Button
          variant="secondary"
          onClick={() => {
            setMessage("");
            requestInfoMutation.reset();
            setRequestInfoOpen(true);
          }}
        >
          Request more information
        </Button>
      </div>

      {pendingDecision && (
        <Modal title={`${titleCase(pendingDecision)} claim ${claim.claim_number}`} onClose={closeDecisionModal}>
          <div className="space-y-4">
            {isOverride && (
              <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800 ring-1 ring-inset ring-amber-200">
                This overrides the AI's recommendation of <strong>{titleCase(packet.recommendation_type!)}</strong>.
              </p>
            )}

            {pendingDecision === "approved" && (
              <label className="block text-sm">
                <span className="mb-1 block font-medium text-slate-700">Approved amount</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={approvedAmount}
                  onChange={(event) => setApprovedAmount(event.target.value)}
                  className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-600"
                />
                <span className="mt-1 block text-xs text-slate-500">
                  Billed amount was {formatCurrency(claim.billed_amount)}.
                </span>
              </label>
            )}

            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Reason</span>
              <textarea
                required
                rows={3}
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-600"
                placeholder="Why are you making this decision?"
              />
            </label>

            {decisionMutation.isError && (
              <ErrorState
                message={
                  decisionMutation.error instanceof ApiError
                    ? decisionMutation.error.message
                    : "Something went wrong submitting this decision."
                }
              />
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={closeDecisionModal}>
                Cancel
              </Button>
              <Button
                variant={pendingDecision === "approved" ? "primary" : "danger"}
                onClick={submitDecision}
                disabled={!reason.trim() || decisionMutation.isPending}
              >
                {decisionMutation.isPending ? "Submitting…" : `Confirm ${pendingDecision}`}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {requestInfoOpen && (
        <Modal title={`Request more information — ${claim.claim_number}`} onClose={() => setRequestInfoOpen(false)}>
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-700">Message to the member</span>
              <textarea
                required
                rows={3}
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-emerald-600"
                placeholder="What do you need from the member?"
              />
              <span className="mt-1 block text-xs text-slate-500">
                This marks the claim as waiting on the member and shows this message in their claim's progress timeline.
              </span>
            </label>

            {requestInfoMutation.isError && (
              <ErrorState
                message={
                  requestInfoMutation.error instanceof ApiError
                    ? requestInfoMutation.error.message
                    : "Something went wrong sending this request."
                }
              />
            )}

            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setRequestInfoOpen(false)}>
                Cancel
              </Button>
              <Button onClick={submitRequestInfo} disabled={!message.trim() || requestInfoMutation.isPending}>
                {requestInfoMutation.isPending ? "Sending…" : "Send request"}
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  );
}
