import { apiClient } from './client';
import type {
  AppSettingsResponse,
  AppSettingsUpdate,
  IntegrationsStatusResponse,
  IntegrationResponse,
} from '../types';

export const settingsApi = {
  get: (): Promise<AppSettingsResponse> => apiClient.get('/settings/'),

  update: (patch: AppSettingsUpdate): Promise<AppSettingsResponse> => apiClient.patch('/settings/', patch),

  getIntegrationsStatus: (): Promise<IntegrationsStatusResponse> => apiClient.get('/integrations/'),

  testIntegration: (provider: string): Promise<IntegrationResponse> =>
    apiClient.post(`/integrations/${provider}/test`),
};
