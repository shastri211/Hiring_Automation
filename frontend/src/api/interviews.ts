import { apiClient } from './client';
import type { PaginatedResponse, GlobalInterviewResponse } from '../types';

export interface GlobalInterviewsParams {
  status?: string;
  job_id?: number;
  page?: number;
  page_size?: number;
}

export const interviewsApi = {
  listGlobal: (params?: GlobalInterviewsParams): Promise<PaginatedResponse<GlobalInterviewResponse>> =>
    apiClient.get('/interviews/', { params }),
};
