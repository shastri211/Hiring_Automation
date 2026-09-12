import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { interviewAnalysisApi, type InterviewAnalysisListParams } from '../api/interviewAnalysis';
import { queryKeys } from '../api/queryKeys';

export const useInterviewAnalysisSummary = (jobId?: number) => {
  return useQuery({
    queryKey: queryKeys.interviewAnalysisSummary(jobId),
    queryFn: () => interviewAnalysisApi.getSummary(jobId),
  });
};

export const useInterviewAnalysisList = (params?: InterviewAnalysisListParams) => {
  return useQuery({
    queryKey: queryKeys.interviewAnalysisList(params),
    queryFn: () => interviewAnalysisApi.list(params),
    placeholderData: keepPreviousData,
  });
};
