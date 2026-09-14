import { useQuery } from '@tanstack/react-query';
import { candidatesApi } from '../api/candidates';
import { queryKeys } from '../api/queryKeys';

export const useShortlistedCandidates = (page = 1, pageSize = 20) => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: [...queryKeys.shortlisted(), page, pageSize],
    queryFn: () => candidatesApi.getGlobalCandidates({ decision: 'SHORTLIST', page, page_size: pageSize }),
  });

  return {
    candidates: data?.items || [],
    total: data?.total || 0,
    page: data?.page || 1,
    pageSize: data?.page_size || 20,
    isLoading,
    isError,
    refetch,
  };
};
