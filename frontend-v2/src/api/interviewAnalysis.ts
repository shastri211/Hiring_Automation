import { apiClient } from './client';
import type { InterviewAnalysisSummaryResponse, InterviewAnalysisItem, PaginatedResponse } from '../types';

export interface InterviewAnalysisListParams {
  job_id?: number;
  disposition?: string;
  page?: number;
  page_size?: number;
}

export const interviewAnalysisApi = {
  getSummary: (jobId?: number): Promise<InterviewAnalysisSummaryResponse> =>
    apiClient.get('/interview-analysis/summary', { params: jobId != null ? { job_id: jobId } : {} }),

  list: (params?: InterviewAnalysisListParams): Promise<PaginatedResponse<InterviewAnalysisItem>> =>
    apiClient.get('/interview-analysis/', { params }),
};
