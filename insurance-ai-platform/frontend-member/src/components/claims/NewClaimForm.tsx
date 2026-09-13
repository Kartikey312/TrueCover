import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { useFileClaim, useMemberPolicies, useProviders } from "../../api/queries";
import type { ClaimType } from "../../api/types";
import { useMemberIdentity } from "../../context/MemberContext";
import { titleCase } from "../../lib/format";
import { Button } from "../ui/Button";
import { ErrorState } from "../ui/Feedback";

const CLAIM_TYPES: ClaimType[] = ["medical", "dental", "vision", "pharmacy", "other"];

export function NewClaimForm() {
  const { memberId } = useMemberIdentity();
  const navigate = useNavigate();
  const { data: policies } = useMemberPolicies(memberId);
  const { data: providers } = useProviders();
  const fileClaim = useFileClaim();

  const [policyId, setPolicyId] = useState("");
  const [claimType, setClaimType] = useState<ClaimType>("medical");
  const [providerId, setProviderId] = useState("");
  const [dateOfService, setDateOfService] = useState("");
  const [billedAmount, setBilledAmount] = useState("");
  const [files, setFiles] = useState<File[]>([]);

  if (!memberId) {
    return <ErrorState message="Select who you are (top right) before filing a claim." />;
  }

  const canSubmit = policyId && claimType && dateOfService && !fileClaim.isPending;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!memberId) return;

    fileClaim.mutate(
      {
        claim: {
          member_id: memberId,
          policy_id: policyId,
          provider_id: providerId || null,
          claim_type: claimType,
          date_of_service: dateOfService,
          billed_amount: billedAmount || null,
        },
        files,
      },
      {
        onSuccess: (claim) => navigate(`/claims/${claim.claim_id}`),
      },
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Which policy is this for?</span>
        <select
          required
          value={policyId}
          onChange={(event) => setPolicyId(event.target.value)}
          className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
        >
          <option value="">Select a policy…</option>
          {policies?.map((policy) => (
            <option key={policy.policy_id} value={policy.policy_id}>
              {policy.plan_name} ({policy.policy_number})
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">What kind of claim is this?</span>
        <select
          value={claimType}
          onChange={(event) => setClaimType(event.target.value as ClaimType)}
          className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
        >
          {CLAIM_TYPES.map((type) => (
            <option key={type} value={type}>
              {titleCase(type)}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Provider (optional)</span>
        <select
          value={providerId}
          onChange={(event) => setProviderId(event.target.value)}
          className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
        >
          <option value="">Not sure / not listed</option>
          {providers?.map((provider) => (
            <option key={provider.provider_id} value={provider.provider_id}>
              {provider.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Date of service</span>
        <input
          type="date"
          required
          value={dateOfService}
          onChange={(event) => setDateOfService(event.target.value)}
          className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600"
        />
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">Billed amount (optional)</span>
        <input
          type="number"
          step="0.01"
          min="0"
          value={billedAmount}
          onChange={(event) => setBilledAmount(event.target.value)}
          placeholder="Leave blank if you're not sure -- we can read it off your invoice"
          className="w-full rounded-md border-slate-300 shadow-sm ring-1 ring-inset ring-slate-300 placeholder:text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
        />
      </label>

      <label className="block text-sm">
        <span className="mb-1 block font-medium text-slate-700">
          Upload your invoice or claim form (PDF or text)
        </span>
        <input
          type="file"
          multiple
          accept=".pdf,.txt,application/pdf,text/plain"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-blue-50 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-blue-700 hover:file:bg-blue-100"
        />
        <span className="mt-1 block text-xs text-slate-500">
          We'll read the amount and procedure codes off this if you didn't enter them above.
        </span>
      </label>

      {fileClaim.isError && (
        <ErrorState
          message={
            fileClaim.error instanceof ApiError
              ? fileClaim.error.message
              : "Something went wrong filing your claim."
          }
        />
      )}

      <Button type="submit" variant="primary" disabled={!canSubmit}>
        {fileClaim.isPending ? "Submitting…" : "Submit claim"}
      </Button>
    </form>
  );
}
