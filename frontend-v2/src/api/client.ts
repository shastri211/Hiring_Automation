import axios, { AxiosError } from 'axios';
import type { ApiError } from '../types';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Centralized response/error interceptor
apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    // Transform raw axios error into our typed ApiError
    const apiError: ApiError = {
      message: 'An unexpected error occurred',
      status: error.response?.status,
    };

    if (error.response?.data) {
      const data = error.response.data as any;
      apiError.message = data.detail || data.message || apiError.message;
      apiError.details = data;
    } else if (error.request) {
      apiError.message = 'No response received from server. Please check your connection.';
    } else {
      apiError.message = error.message;
    }

    return Promise.reject(apiError);
  }
);
