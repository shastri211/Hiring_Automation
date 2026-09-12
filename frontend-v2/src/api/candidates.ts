import { apiClient } from './client';
import type { PaginatedResponse, GlobalScreeningResultResponse, ScreeningResultsParams } from '../types';

export const candidatesApi = {
  getGlobalCandidates: (params?: ScreeningResultsParams) => {
    return apiClient.get<any>('/candidates/', { params }) as unknown as Promise<PaginatedResponse<GlobalScreeningResultResponse>>;
  },
};
