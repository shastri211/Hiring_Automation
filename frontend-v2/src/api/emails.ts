import { apiClient } from './client';
import type {
  EmailTemplate,
  EmailTemplateCreate,
  EmailTemplateUpdate,
  EmailMessage,
  EmailMessageGlobalResponse,
  BulkEmailRequest,
  PaginatedResponse,
} from '../types';

export interface EmailMessagesParams {
  status?: string;
  job_id?: number;
  page?: number;
  page_size?: number;
}

export const emailsApi = {
  getTemplates: async (): Promise<EmailTemplate[]> => {
    return apiClient.get('/emails/templates');
  },

  createTemplate: async (template: EmailTemplateCreate): Promise<EmailTemplate> => {
    return apiClient.post('/emails/templates', template);
  },

  updateTemplate: async (id: number, patch: EmailTemplateUpdate): Promise<EmailTemplate> => {
    return apiClient.patch(`/emails/templates/${id}`, patch);
  },

  deleteTemplate: async (id: number): Promise<void> => {
    return apiClient.delete(`/emails/templates/${id}`);
  },

  bulkSend: async (jobId: number, request: BulkEmailRequest): Promise<{status: string, queued_count: number}> => {
    return apiClient.post(`/emails/jobs/${jobId}/bulk-send`, request);
  },

  getCandidateEmails: async (resumeId: number): Promise<EmailMessage[]> => {
    return apiClient.get(`/emails/candidates/${resumeId}`);
  },

  listMessages: async (params?: EmailMessagesParams): Promise<PaginatedResponse<EmailMessageGlobalResponse>> => {
    return apiClient.get('/emails/messages', { params });
  }
};
