import { apiClient } from './client';
import type { IntegrationResponse } from '../types';

export const integrationApi = {
  triggerInterview: async (jobId: number, resumeId: number): Promise<IntegrationResponse> => {
    return apiClient.post('/integration/interview/trigger', {
      job_id: jobId,
      resume_id: resumeId,
    });
  },
};
