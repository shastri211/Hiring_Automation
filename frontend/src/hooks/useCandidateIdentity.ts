import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { candidatesApi } from '../api/candidates';
import { queryKeys } from '../api/queryKeys';
import type { MatchSuggestionStatus, MergeCandidatesRequest } from '../types';

export const useMatchSuggestions = (status: MatchSuggestionStatus = 'PENDING') => {
  return useQuery({
    queryKey: queryKeys.matchSuggestions(status),
    queryFn: () => candidatesApi.getMatchSuggestions(status),
  });
};

export const useCandidate = (candidateId: number | null | undefined) => {
  return useQuery({
    queryKey: queryKeys.candidate(candidateId ?? 0),
    queryFn: () => candidatesApi.getCandidate(candidateId as number),
    enabled: candidateId != null,
  });
};

export const useCandidateSearch = (term: string, excludeId?: number) => {
  const trimmed = term.trim();
  return useQuery({
    queryKey: queryKeys.candidateSearch(trimmed, excludeId),
    queryFn: () => candidatesApi.searchCandidates(trimmed, excludeId),
    enabled: trimmed.length >= 2,
  });
};

// Every mutation below invalidates all match-suggestion status buckets
// (PENDING/MERGED/REJECTED) since a suggestion moves between them, plus the
// 'candidate' cache for both parties so a Candidate360 view open elsewhere
// picks up the new merge state immediately. Also invalidates every
// global-candidates and candidate-detail query app-wide (no jobId/resumeId
// is known here, only candidate ids) since a merge changes the canonical
// display_name/candidate_id/applications_count those list/detail views show
// for any resume tied to either candidate - without this they silently kept
// showing pre-merge data until their 5-minute staleTime lapsed.
const invalidateSuggestionsAndCandidates = (
  queryClient: ReturnType<typeof useQueryClient>,
  candidateIds: number[]
) => {
  queryClient.invalidateQueries({ queryKey: ['match-suggestions'] });
  queryClient.invalidateQueries({ queryKey: ['global-candidates'] });
  queryClient.invalidateQueries({ queryKey: ['candidate-detail'] });
  queryClient.invalidateQueries({ queryKey: ['candidate-search'] });
  candidateIds.forEach((id) => {
    queryClient.invalidateQueries({ queryKey: queryKeys.candidate(id) });
  });
};

export const useMergeMatchSuggestion = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (suggestionId: number) => candidatesApi.mergeMatchSuggestion(suggestionId),
    onSuccess: (suggestion) => {
      invalidateSuggestionsAndCandidates(queryClient, [suggestion.candidate_a_id, suggestion.candidate_b_id]);
      toast.success('Candidates merged.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not merge candidates.');
    },
  });
};

export const useRejectMatchSuggestion = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (suggestionId: number) => candidatesApi.rejectMatchSuggestion(suggestionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['match-suggestions'] });
      toast.success('Suggestion dismissed.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not dismiss suggestion.');
    },
  });
};

export const useMergeCandidates = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: MergeCandidatesRequest) => candidatesApi.mergeCandidates(payload),
    onSuccess: (_, variables) => {
      invalidateSuggestionsAndCandidates(queryClient, [variables.absorbed_candidate_id, variables.into_candidate_id]);
      toast.success('Candidates merged.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not merge candidates.');
    },
  });
};

export const useUnmergeCandidate = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (candidateId: number) => candidatesApi.unmergeCandidate(candidateId),
    onSuccess: (result) => {
      invalidateSuggestionsAndCandidates(queryClient, [result.absorbed_candidate_id, result.into_candidate_id]);
      toast.success('Merge reversed.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not reverse merge.');
    },
  });
};

export const useUpdateCandidateName = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ candidateId, canonicalName }: { candidateId: number; canonicalName: string | null }) =>
      candidatesApi.updateCandidateName(candidateId, { canonical_name: canonicalName }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.candidate(variables.candidateId) });
      toast.success('Candidate name updated.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not update name.');
    },
  });
};
