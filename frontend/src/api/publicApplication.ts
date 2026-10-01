import { apiClient } from './client';
import type { PublicJobResponse } from '../types';

// Unauthenticated by design - auth here is possession of the job's opaque
// application token (see app/api/public_application.py).
export const publicApplicationApi = {
  getJob: (token: string): Promise<PublicJobResponse> => {
    return apiClient.get<any>(`/public/jobs/${token}`) as unknown as Promise<PublicJobResponse>;
  },

  apply: (token: string, formData: FormData): Promise<{ status: string }> => {
    return apiClient.post<any>(`/public/jobs/${token}/apply`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }) as unknown as Promise<{ status: string }>;
  },
};
