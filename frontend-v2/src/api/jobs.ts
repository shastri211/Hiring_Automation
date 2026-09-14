import { apiClient } from './client';
import type {
  Job,
  ScreeningResultResponse,
  PaginatedResponse,
  UploadResponse,
  BatchProgressResponse,
  CandidateDetailResponse,
  ScreeningResultsParams,
  JobBatchOverviewItem,
} from '../types';

export const jobsApi = {
  getJobs: () => {
    return apiClient.get<any>('/jobs/') as unknown as Promise<Job[]>;
  },
  
  getJob: (jobId: number) => {
    return apiClient.get<any>(`/jobs/${jobId}`) as unknown as Promise<Job>;
  },
  
  createJobFromUpload: (formData: FormData) => {
    return apiClient.post<any>('/jobs/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }) as unknown as Promise<Job>;
  },
  
  uploadResumes: (jobId: number, formData: FormData, onUploadProgress?: (progressEvent: any) => void) => {
    return apiClient.post<any>(`/resumes/upload/${jobId}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress,
    }) as unknown as Promise<UploadResponse>;
  },
  
  screenJob: (jobId: number) => {
    return apiClient.post<any>(`/jobs/${jobId}/screen`) as unknown as Promise<{ message: string; batch_id: number }>;
  },
  
  getJobProgress: (jobId: number) => {
    return apiClient.get<any>(`/jobs/${jobId}/progress`) as unknown as Promise<BatchProgressResponse>;
  },

  getBatchesOverview: () => {
    return apiClient.get<any>('/jobs/batches/overview') as unknown as Promise<JobBatchOverviewItem[]>;
  },
  
  getJobResults: (jobId: number, params?: ScreeningResultsParams) => {
    return apiClient.get<any>(`/jobs/${jobId}/results`, { params }) as unknown as Promise<PaginatedResponse<ScreeningResultResponse>>;
  },
  
  getJobResultDetail: (jobId: number, resumeId: number) => {
    return apiClient.get<any>(`/jobs/${jobId}/results/${resumeId}`) as unknown as Promise<CandidateDetailResponse>;
  },
  
  updateDecision: (jobId: number, resumeId: number, decision: string | null, notes?: string) => {
    return apiClient.patch<any>(`/jobs/${jobId}/results/${resumeId}/decision`, { decision, notes }) as unknown as Promise<ScreeningResultResponse>;
  },
  
  bulkUpdateDecision: (jobId: number, resumeIds: number[], decision: string | null) => {
    return apiClient.patch<any>(`/jobs/${jobId}/results/bulk-decision`, { resume_ids: resumeIds, decision }) as unknown as Promise<{ message: string; updated_count: number }>;
  },

  pauseJob: (jobId: number) => {
    return apiClient.post<any>(`/jobs/${jobId}/pause`) as unknown as Promise<Job>;
  },

  resumeJob: (jobId: number) => {
    return apiClient.post<any>(`/jobs/${jobId}/resume`) as unknown as Promise<Job>;
  },

  archiveJob: (jobId: number) => {
    return apiClient.post<any>(`/jobs/${jobId}/archive`) as unknown as Promise<Job>;
  },

  deleteJob: (jobId: number) => {
    return apiClient.delete<any>(`/jobs/${jobId}`) as unknown as Promise<void>;
  },

  resyncInterview: (jobId: number, resumeId: number) => {
    return apiClient.post<any>(`/jobs/${jobId}/interviews/${resumeId}/resync`) as unknown as Promise<{ success: boolean; message: string }>;
  }
};
