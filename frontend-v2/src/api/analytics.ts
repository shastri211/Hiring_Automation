import { apiClient } from './client';
import type {
  FunnelResponse,
  DecisionBreakdownResponse,
  ThroughputResponse,
  TimeInStageResponse,
  JobVolumeResponse,
} from '../types';

export const analyticsApi = {
  getFunnel: (jobId?: number): Promise<FunnelResponse> =>
    apiClient.get('/analytics/funnel', { params: jobId != null ? { job_id: jobId } : {} }),

  getDecisionBreakdown: (jobId?: number): Promise<DecisionBreakdownResponse> =>
    apiClient.get('/analytics/decisions', { params: jobId != null ? { job_id: jobId } : {} }),

  getThroughput: (days = 30, jobId?: number): Promise<ThroughputResponse> =>
    apiClient.get('/analytics/throughput', { params: { days, ...(jobId != null ? { job_id: jobId } : {}) } }),

  getTimeInStage: (jobId?: number): Promise<TimeInStageResponse> =>
    apiClient.get('/analytics/time-in-stage', { params: jobId != null ? { job_id: jobId } : {} }),

  getJobVolume: (): Promise<JobVolumeResponse> => apiClient.get('/analytics/job-volume'),
};
