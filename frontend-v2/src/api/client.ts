import axios, { AxiosError } from 'axios';
import type { ApiError } from '../types';
import { notifyPasswordChangeRequired, notifyUnauthorized } from './authEvents';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
  // Send the httpOnly `access_token` session cookie on cross-origin requests
  // (dev: frontend on :5173, backend on :8001). Backend CORS already sets
  // allow_credentials: true with an explicit origin list.
  withCredentials: true,
});

// Paths that are never subject to HR-session auth: the auth endpoints
// themselves (a 401 from /auth/me or /auth/login is expected, normal
// "not logged in" signal, not a session-expiry event) and the public,
// candidate-facing interview room and apply page (which never have an HR
// session cookie at all and must never be redirected to the HR login).
const AUTH_EXEMPT_PREFIXES = ['/auth/', '/public/interview/', '/public/jobs/'];

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
      // FastAPI's 422 `detail` is an array of {loc, msg, type} validation
      // errors, not a string - falling through to `data.message` (usually
      // undefined) silently dropped every Pydantic validation message and
      // left the generic "An unexpected error occurred" in its place.
      if (typeof data.detail === 'string') {
        apiError.message = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        apiError.message = data.detail
          .map((d: any) => (typeof d?.msg === 'string' ? d.msg.replace(/^Value error,\s*/, '') : null))
          .filter(Boolean)
          .join('; ') || apiError.message;
      } else if (data.detail && typeof data.detail === 'object' && typeof data.detail.message === 'string') {
        // Structured {reason, message} details (auth/signup/tenancy errors).
        apiError.message = data.detail.message;
      } else if (typeof data.message === 'string') {
        apiError.message = data.message;
      }
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
    // The account is still on an admin-issued temporary password: every
    // route but /auth/me and /auth/change-password refuses it. Re-read the
    // session so RequireAuth routes to the change-password screen.
    if (
      error.response?.status === 403 &&
      (error.response?.data as any)?.detail?.reason === 'password_change_required'
    ) {
      notifyPasswordChangeRequired();
    }

    return Promise.reject(apiError);
  }
);
