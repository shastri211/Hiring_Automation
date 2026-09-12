import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { toast } from 'sonner';
import { talentPoolApi, type TalentPoolListParams } from '../api/talentPool';
import { queryKeys } from '../api/queryKeys';
import type { TalentPoolEntryCreate, TalentPoolEntryUpdate } from '../types';

export const useTalentPool = (params?: TalentPoolListParams) => {
  return useQuery({
    queryKey: queryKeys.talentPool(params),
    queryFn: () => talentPoolApi.list(params),
    placeholderData: keepPreviousData,
  });
};

/**
 * Shared "Add to Talent Pool" mutation — reused as-is by GlobalCandidates.tsx,
 * JobCandidates.tsx, Candidate360.tsx, and Shortlisted.tsx. Call shape:
 *   useAddToTalentPool().mutate({ resume_id, added_from_job_id })
 * Toasts are baked in here so every entry point gets identical feedback
 * without duplicating toast copy at each call site.
 */
export const useAddToTalentPool = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: TalentPoolEntryCreate) => talentPoolApi.add(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['talent-pool'] });
      toast.success('Added to Talent Pool.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not add to Talent Pool.');
    },
  });
};

export const useUpdateTalentPoolEntry = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: TalentPoolEntryUpdate }) => talentPoolApi.update(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['talent-pool'] });
      toast.success('Talent Pool entry updated.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not update entry.');
    },
  });
};

export const useRemoveFromTalentPool = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => talentPoolApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['talent-pool'] });
      toast.success('Removed from Talent Pool.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Could not remove entry.');
    },
  });
};
