import type { ScreeningResultsParams } from '../types';
import type { TalentPoolListParams } from './talentPool';
import type { GlobalInterviewsParams } from './interviews';
import type { InterviewAnalysisListParams } from './interviewAnalysis';
import type { EmailMessagesParams } from './emails';

export const queryKeys = {
  jobs: () => ['jobs'] as const,
  job: (id: number) => ['job', id] as const,
  jobProgress: (id: number) => ['job-progress', id] as const,
  candidates: (jobId: number, params?: ScreeningResultsParams) =>
    params ? ['candidates', jobId, params] as const : ['candidates', jobId] as const,
  candidateDetail: (jobId: number, resumeId: number) => ['candidate-detail', jobId, resumeId] as const,
  shortlisted: () => ['shortlisted'] as const,

  globalCandidates: (params?: ScreeningResultsParams) =>
    params ? (['global-candidates', params] as const) : (['global-candidates'] as const),

  settings: () => ['settings'] as const,
  integrationsStatus: () => ['integrations-status'] as const,

  authUsers: () => ['auth-users'] as const,

  talentPool: (params?: TalentPoolListParams) =>
    params ? (['talent-pool', params] as const) : (['talent-pool'] as const),

  globalInterviews: (params?: GlobalInterviewsParams) =>
    params ? (['global-interviews', params] as const) : (['global-interviews'] as const),

  analyticsFunnel: (jobId?: number) => ['analytics-funnel', jobId ?? null] as const,
  analyticsDecisions: (jobId?: number) => ['analytics-decisions', jobId ?? null] as const,
  analyticsThroughput: (days: number, jobId?: number) => ['analytics-throughput', days, jobId ?? null] as const,
  analyticsTimeInStage: (jobId?: number) => ['analytics-time-in-stage', jobId ?? null] as const,
  analyticsJobVolume: () => ['analytics-job-volume'] as const,

  interviewAnalysisSummary: (jobId?: number) => ['interview-analysis-summary', jobId ?? null] as const,
  interviewAnalysisList: (params?: InterviewAnalysisListParams) =>
    params ? (['interview-analysis-list', params] as const) : (['interview-analysis-list'] as const),

  emailMessages: (params?: EmailMessagesParams) =>
    params ? (['email-messages', params] as const) : (['email-messages'] as const),
};
