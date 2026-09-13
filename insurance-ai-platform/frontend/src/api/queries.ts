import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  AdjusterQueueItem,
  ClaimDecisionCreate,
  ClaimDocumentRead,
  ClaimRead,
  ClaimReviewPacket,
  RequestInfoCreate,
  TimelineEvent,
} from "./types";

export function useQueue(adjusterId: string | null) {
  return useQuery({
    queryKey: ["queue", adjusterId],
    queryFn: () =>
      api.get<AdjusterQueueItem[]>(adjusterId ? `/adjuster/queue?adjuster_id=${adjusterId}` : "/adjuster/queue"),
    refetchInterval: 15_000,
  });
}

export function useClaim(claimId: string) {
  return useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => api.get<ClaimRead>(`/claims/${claimId}`),
  });
}

export function useReviewPacket(claimId: string) {
  return useQuery({
    queryKey: ["review", claimId],
    queryFn: () => api.get<ClaimReviewPacket>(`/claims/${claimId}/review`),
  });
}

export function useDocuments(claimId: string) {
  return useQuery({
    queryKey: ["documents", claimId],
    queryFn: () => api.get<ClaimDocumentRead[]>(`/claims/${claimId}/documents`),
  });
}

export function useTimeline(claimId: string) {
  return useQuery({
    queryKey: ["timeline", claimId],
    queryFn: () => api.get<TimelineEvent[]>(`/claims/${claimId}/timeline`),
  });
}

function useInvalidateClaim(claimId: string) {
  const queryClient = useQueryClient();
  return () => {
    queryClient.invalidateQueries({ queryKey: ["claim", claimId] });
    queryClient.invalidateQueries({ queryKey: ["review", claimId] });
    queryClient.invalidateQueries({ queryKey: ["timeline", claimId] });
    queryClient.invalidateQueries({ queryKey: ["queue"] });
  };
}

export function useSubmitClaim(claimId: string) {
  const invalidate = useInvalidateClaim(claimId);
  return useMutation({
    mutationFn: () => api.post<ClaimRead>(`/claims/${claimId}/submit`),
    onSuccess: invalidate,
  });
}

export function useDecision(claimId: string) {
  const invalidate = useInvalidateClaim(claimId);
  return useMutation({
    mutationFn: (payload: ClaimDecisionCreate) => api.post<ClaimRead>(`/claims/${claimId}/decision`, payload),
    onSuccess: invalidate,
  });
}

export function useRequestInfo(claimId: string) {
  const invalidate = useInvalidateClaim(claimId);
  return useMutation({
    mutationFn: (payload: RequestInfoCreate) => api.post<ClaimRead>(`/claims/${claimId}/request-info`, payload),
    onSuccess: invalidate,
  });
}
