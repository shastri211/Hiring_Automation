import { apiClient } from './client';

export const resumesApi = {
  getResumeFileUrl: (resumeId: number) => {
    return `${apiClient.defaults.baseURL}/resumes/file/${resumeId}`;
  }
};
