import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { emailsApi } from '../api/emails';
import type { EmailTemplateCreate, BulkEmailRequest } from '../types';

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
