import { useQuery } from '@tanstack/react-query';
import { analyticsApi } from '../api/analytics';
import { queryKeys } from '../api/queryKeys';

export const useFunnel = (jobId?: number) => {
  return useQuery({
    queryKey: queryKeys.analyticsFunnel(jobId),
    queryFn: () => analyticsApi.getFunnel(jobId),
  });
};

export const useDecisionBreakdown = (jobId?: number) => {
  return useQuery({
    queryKey: queryKeys.analyticsDecisions(jobId),
    queryFn: () => analyticsApi.getDecisionBreakdown(jobId),
  });
};

export const useThroughput = (days = 30, jobId?: number) => {
  return useQuery({
    queryKey: queryKeys.analyticsThroughput(days, jobId),
    queryFn: () => analyticsApi.getThroughput(days, jobId),
  });
};

export const useTimeInStage = (jobId?: number) => {
  return useQuery({
    queryKey: queryKeys.analyticsTimeInStage(jobId),
    queryFn: () => analyticsApi.getTimeInStage(jobId),
  });
};

export const useJobVolume = () => {
  return useQuery({
    queryKey: queryKeys.analyticsJobVolume(),
    queryFn: analyticsApi.getJobVolume,
  });
};
