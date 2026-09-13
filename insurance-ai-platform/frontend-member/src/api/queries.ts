import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  ClaimCreate,
  ClaimDocumentRead,
  ClaimRead,
  MemberPolicyRead,
  ProviderRead,
  TimelineEvent,
} from "./types";

export function useMemberPolicies(memberId: string | null) {
  return useQuery({
    queryKey: ["member-policies", memberId],
    queryFn: () => api.get<MemberPolicyRead[]>(`/members/${memberId}/policies`),
    enabled: !!memberId,
  });
}

export function useMemberClaims(memberId: string | null) {
  return useQuery({
    queryKey: ["member-claims", memberId],
    queryFn: () => api.get<ClaimRead[]>(`/members/${memberId}/claims`),
    enabled: !!memberId,
    refetchInterval: 15_000,
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api.get<ProviderRead[]>("/providers"),
  });
}

export function useClaim(claimId: string) {
  return useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => api.get<ClaimRead>(`/claims/${claimId}`),
    refetchInterval: 15_000,
  });
}

export function useClaimDocuments(claimId: string) {
  return useQuery({
    queryKey: ["claim-documents", claimId],
    queryFn: () => api.get<ClaimDocumentRead[]>(`/claims/${claimId}/documents`),
  });
}

export function useClaimTimeline(claimId: string) {
  return useQuery({
    queryKey: ["claim-timeline", claimId],
    queryFn: () => api.get<TimelineEvent[]>(`/claims/${claimId}/timeline`),
    refetchInterval: 15_000,
  });
}

interface FileClaimInput {
  claim: ClaimCreate;
  files: File[];
}

/** Creates the claim, uploads every attached file, then submits it for AI
 * review -- presented to the member as one atomic action even though it's
 * three API calls under the hood.
 */
export function useFileClaim() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ claim, files }: FileClaimInput) => {
      const created = await api.post<ClaimRead>("/claims", claim);

      for (const file of files) {
        const formData = new FormData();
        formData.append("document_type", "invoice");
        formData.append("file", file);
        await api.post(`/claims/${created.claim_id}/documents`, formData);
      }

      return api.post<ClaimRead>(`/claims/${created.claim_id}/submit`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["member-claims"] });
    },
  });
}
