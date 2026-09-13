import axios, { AxiosError } from 'axios';
import type { ApiError } from '../types';
import { notifyUnauthorized } from './authEvents';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  // Send the httpOnly `access_token` session cookie on cross-origin requests
  // (dev: frontend on :5173, backend on :8000). Backend CORS already sets
  // allow_credentials: true with an explicit origin list.
  withCredentials: true,
});

// Paths that are never subject to HR-session auth: the auth endpoints
// themselves (a 401 from /auth/me or /auth/login is expected, normal
// "not logged in" signal, not a session-expiry event) and the public,
// candidate-facing interview room (which never has an HR session cookie at
// all and must never be redirected to the HR login).
const AUTH_EXEMPT_PREFIXES = ['/auth/', '/public/interview/'];

const isAuthExempt = (url?: string): boolean => {
  if (!url) return false;
  // Strip a leading baseURL if the request URL happens to be absolute.
  const path = url.replace(/^https?:\/\/[^/]+/, '');
  return AUTH_EXEMPT_PREFIXES.some((prefix) => path.includes(prefix));
};

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

    // A 401 from any request other than the auth/public-interview endpoints
    // means the HR session cookie expired or was revoked mid-session. Notify
    // whoever registered interest (AuthProvider) so it can clear the user and
    // let RequireAuth redirect to /login.
    if (error.response?.status === 401 && !isAuthExempt(error.config?.url)) {
      notifyUnauthorized();
    }

    return Promise.reject(apiError);
  }
);
