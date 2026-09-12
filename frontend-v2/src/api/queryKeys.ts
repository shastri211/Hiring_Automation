import type { ScreeningResultsParams } from '../types';

export const queryKeys = {
  jobs: () => ['jobs'] as const,
  job: (id: number) => ['job', id] as const,
  jobProgress: (id: number) => ['job-progress', id] as const,
  candidates: (jobId: number, params?: ScreeningResultsParams) => 
    params ? ['candidates', jobId, params] as const : ['candidates', jobId] as const,
  candidateDetail: (jobId: number, resumeId: number) => ['candidate-detail', jobId, resumeId] as const,
  shortlisted: () => ['shortlisted'] as const,
};
