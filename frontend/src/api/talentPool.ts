import { apiClient } from './client';
import type {
  PaginatedResponse,
  TalentPoolEntry,
  TalentPoolEntryCreate,
  TalentPoolEntryUpdate,
} from '../types';

export interface TalentPoolListParams {
  q?: string;
  tag?: string;
  page?: number;
  page_size?: number;
}

export const talentPoolApi = {
  list: (params?: TalentPoolListParams): Promise<PaginatedResponse<TalentPoolEntry>> =>
    apiClient.get('/talent-pool/', { params }),

  add: (payload: TalentPoolEntryCreate): Promise<TalentPoolEntry> => apiClient.post('/talent-pool/', payload),

  update: (id: number, patch: TalentPoolEntryUpdate): Promise<TalentPoolEntry> =>
    apiClient.patch(`/talent-pool/${id}`, patch),

  remove: (id: number): Promise<void> => apiClient.delete(`/talent-pool/${id}`),
};
