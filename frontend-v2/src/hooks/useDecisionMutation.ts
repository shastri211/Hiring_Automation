import { useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import type { CandidateDecision } from '../types';
import { toast } from 'sonner';

export const useDecisionMutation = (jobId: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ resumeId, decision, notes }: { resumeId: number, decision: CandidateDecision, notes?: string }) => 
      jobsApi.updateDecision(jobId, resumeId, decision, notes),
    onSuccess: (_, { decision }) => {
      // Invalidate candidates list for this job
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      // Invalidate the specific candidate detail
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, 0).slice(0, 2) });
      // Invalidate the global shortlist
      queryClient.invalidateQueries({ queryKey: queryKeys.shortlisted() });
      toast.success(decision ? `Candidate marked for ${decision.toLowerCase()}.` : 'Candidate decision cleared.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Unable to update the candidate decision.');
    }
  });
};
