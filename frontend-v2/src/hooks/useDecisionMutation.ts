import { useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { emailQueryKeys } from './useEmails';
import type { CandidateDecision } from '../types';
import { toast } from 'sonner';

export const useDecisionMutation = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resumeId, decision, notes }: { resumeId: number, decision: CandidateDecision, notes?: string }) =>
      jobsApi.updateDecision(jobId, resumeId, decision, notes),
    onSuccess: (_, { resumeId, decision }) => {
      // Invalidate candidates list for this job
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      // Invalidate the specific candidate detail
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, 0).slice(0, 2) });
      // Invalidate the global shortlist
      queryClient.invalidateQueries({ queryKey: queryKeys.shortlisted() });
      // A SHORTLIST decision can auto-mint an interview link and auto-send an
      // email via outreach_service.on_decision_shortlisted - candidateDetail
      // above covers the interview link, but OutreachHistory (Candidate360)
      // reads its own separate query key, so it needs its own invalidation
      // or the newly auto-sent email won't appear without a manual refresh.
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.candidateHistory(resumeId) });
      toast.success(decision ? `Candidate marked for ${decision.toLowerCase()}.` : 'Candidate decision cleared.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Unable to update the candidate decision.');
    }
  });
};

export const useRetryEvaluation = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (resumeId: number) => jobsApi.retryEvaluation(jobId, resumeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, 0).slice(0, 2) });
      toast.success('Evaluation retried successfully.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Retry failed - the LLM providers may still be unavailable.');
    },
  });
};
