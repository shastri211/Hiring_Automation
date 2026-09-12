import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { toast } from 'sonner';
import { emailsApi, type EmailMessagesParams } from '../api/emails';
import { queryKeys } from '../api/queryKeys';
import type { EmailTemplateCreate, EmailTemplateUpdate, BulkEmailRequest } from '../types';

export const emailQueryKeys = {
  all: ['emails'] as const,
  templates: () => [...emailQueryKeys.all, 'templates'] as const,
  candidateHistory: (resumeId: number) => [...emailQueryKeys.all, 'candidate', resumeId] as const,
};

export const useEmailTemplates = () => {
  return useQuery({
    queryKey: emailQueryKeys.templates(),
    queryFn: emailsApi.getTemplates,
  });
};

export const useCreateTemplate = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (template: EmailTemplateCreate) => emailsApi.createTemplate(template),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.templates() });
    },
  });
};

export const useBulkSendEmails = (jobId: number) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (request: BulkEmailRequest) => emailsApi.bulkSend(jobId, request),
    onSuccess: (_, variables) => {
      // Invalidate history for all involved resumes
      variables.resume_ids.forEach(resumeId => {
        queryClient.invalidateQueries({ queryKey: emailQueryKeys.candidateHistory(resumeId) });
      });
    },
  });
};

export const useCandidateEmails = (resumeId: number) => {
  return useQuery({
    queryKey: emailQueryKeys.candidateHistory(resumeId),
    queryFn: () => emailsApi.getCandidateEmails(resumeId),
    enabled: !!resumeId,
  });
};

export const useUpdateTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: EmailTemplateUpdate }) => emailsApi.updateTemplate(id, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.templates() });
      toast.success('Template updated.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Failed to update template.');
    },
  });
};

export const useDeleteTemplate = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => emailsApi.deleteTemplate(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: emailQueryKeys.templates() });
      toast.success('Template deleted.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Failed to delete template.');
    },
  });
};

export const useEmailMessages = (params?: EmailMessagesParams) => {
  return useQuery({
    queryKey: queryKeys.emailMessages(params),
    queryFn: () => emailsApi.listMessages(params),
    placeholderData: keepPreviousData,
  });
};
