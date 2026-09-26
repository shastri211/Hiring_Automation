import { apiClient } from './client';
import type {
  PaginatedResponse,
  GlobalScreeningResultResponse,
  ScreeningResultsParams,
  CandidateResponse,
  CandidateNameUpdateRequest,
  CandidateMatchSuggestion,
  CandidateMatchSuggestionResponse,
  MatchSuggestionStatus,
  MergeCandidatesRequest,
  UnmergeCandidateResponse,
} from '../types';

export const candidatesApi = {
  getGlobalCandidates: (params?: ScreeningResultsParams) => {
    return apiClient.get<any>('/candidates/', { params }) as unknown as Promise<PaginatedResponse<GlobalScreeningResultResponse>>;
  },

  // Canonical (not merged-away) candidates matching name/email/phone - the
  // manual-merge target picker. `term` must be at least 2 characters.
  searchCandidates: (term: string, excludeId?: number): Promise<CandidateResponse[]> => {
    return apiClient.get('/candidates/search', { params: { q: term, exclude_id: excludeId } });
  },

  getCandidate: (candidateId: number): Promise<CandidateResponse> => {
    return apiClient.get(`/candidates/${candidateId}`);
  },

  updateCandidateName: (candidateId: number, payload: CandidateNameUpdateRequest): Promise<CandidateResponse> => {
    return apiClient.patch(`/candidates/${candidateId}`, payload);
  },

  getMatchSuggestions: (status: MatchSuggestionStatus = 'PENDING'): Promise<CandidateMatchSuggestion[]> => {
    return apiClient.get('/candidates/match-suggestions', { params: { status } });
  },

  mergeMatchSuggestion: (suggestionId: number): Promise<CandidateMatchSuggestionResponse> => {
    return apiClient.post(`/candidates/match-suggestions/${suggestionId}/merge`);
  },

  rejectMatchSuggestion: (suggestionId: number): Promise<CandidateMatchSuggestionResponse> => {
    return apiClient.post(`/candidates/match-suggestions/${suggestionId}/reject`);
  },

  mergeCandidates: (payload: MergeCandidatesRequest): Promise<void> => {
    return apiClient.post('/candidates/merge', payload);
  },

  unmergeCandidate: (candidateId: number): Promise<UnmergeCandidateResponse> => {
    return apiClient.post(`/candidates/${candidateId}/unmerge`);
  },
};
