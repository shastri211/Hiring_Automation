import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { interviewsApi, type GlobalInterviewsParams } from '../api/interviews';
import { queryKeys } from '../api/queryKeys';

export const useGlobalInterviews = (params?: GlobalInterviewsParams) => {
  return useQuery({
    queryKey: queryKeys.globalInterviews(params),
    queryFn: () => interviewsApi.listGlobal(params),
    placeholderData: keepPreviousData,
  });
};
