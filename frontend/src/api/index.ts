import { jobsApi } from './jobs';
import { integrationApi } from './integration';

export { jobsApi, integrationApi };

export const api = {
  jobs: jobsApi,
  integration: integrationApi,
};
