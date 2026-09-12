import { apiClient } from './client';
import type { 
  EmailTemplate, 
  EmailTemplateCreate, 
  EmailMessage, 
  BulkEmailRequest 
} from '../types';

export const emailsApi = {
  getTemplates: async (): Promise<EmailTemplate[]> => {
    return apiClient.get('/emails/templates');
  },
  
  createTemplate: async (template: EmailTemplateCreate): Promise<EmailTemplate> => {
    return apiClient.post('/emails/templates', template);
  },
  
  bulkSend: async (jobId: number, request: BulkEmailRequest): Promise<{status: string, queued_count: number}> => {
    return apiClient.post(`/emails/jobs/${jobId}/bulk-send`, request);
  },
  
  getCandidateEmails: async (resumeId: number): Promise<EmailMessage[]> => {
    return apiClient.get(`/emails/candidates/${resumeId}`);
  }
};
