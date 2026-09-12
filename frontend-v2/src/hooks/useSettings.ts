import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '../api/settings';
import { queryKeys } from '../api/queryKeys';
import type { AppSettingsUpdate } from '../types';

export const useSettings = () => {
  return useQuery({
    queryKey: queryKeys.settings(),
    queryFn: settingsApi.get,
  });
};

export const useUpdateSettings = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (patch: AppSettingsUpdate) => settingsApi.update(patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings() });
    },
  });
};

export const useIntegrationsStatus = () => {
  return useQuery({
    queryKey: queryKeys.integrationsStatus(),
    queryFn: settingsApi.getIntegrationsStatus,
  });
};

export const useTestIntegration = () => {
  return useMutation({
    mutationFn: (provider: string) => settingsApi.testIntegration(provider),
  });
};
