import { apiClient } from './client';
import type { PublicInterviewRoomResponse } from '../types';

// Unauthenticated by design - auth here is possession of the opaque token,
// not identity (see app/api/public_interview.py). Never send credentials.
export const publicInterviewApi = {
  get: (token: string): Promise<PublicInterviewRoomResponse> => {
    return apiClient.get<any>(`/public/interview/${token}`) as unknown as Promise<PublicInterviewRoomResponse>;
  },

  markStarted: (token: string): Promise<{ success: boolean }> => {
    return apiClient.post<any>(`/public/interview/${token}/started`) as unknown as Promise<{ success: boolean }>;
  },
};
