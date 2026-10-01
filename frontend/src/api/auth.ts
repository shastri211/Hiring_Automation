import { apiClient } from './client';
import type {
  ChangePasswordRequest, LoginRequest, MeResponse, SignupRequest, UserCreate, UserResponse, UserUpdate,
} from '../types';

export const authApi = {
  login: (payload: LoginRequest): Promise<MeResponse> => apiClient.post('/auth/login', payload),

  logout: (): Promise<{ success: boolean }> => apiClient.post('/auth/logout'),

  getMe: (): Promise<MeResponse> => apiClient.get('/auth/me'),

  changePassword: (payload: ChangePasswordRequest): Promise<{ success: boolean }> =>
    apiClient.post('/auth/change-password', payload),

  // Public - always the same generic 202 {status: "check_inbox"}.
  signup: (payload: SignupRequest): Promise<{ status: string }> => apiClient.post('/auth/signup', payload),

  verifyEmail: (token: string): Promise<{ status: string }> => apiClient.post('/auth/verify-email', { token }),

  resendVerification: (email: string): Promise<{ status: string }> =>
    apiClient.post('/auth/resend-verification', { email }),

  // Public - always the same generic 202 {status: "check_inbox"}.
  forgotPassword: (email: string): Promise<{ status: string }> =>
    apiClient.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, newPassword: string): Promise<{ status: string }> =>
    apiClient.post('/auth/reset-password', { token, new_password: newPassword }),

  // Organization user management (admin-only on the server).
  createUser: (payload: UserCreate): Promise<UserResponse> => apiClient.post('/auth/users', payload),

  listUsers: (): Promise<UserResponse[]> => apiClient.get('/auth/users'),

  updateUser: (userId: number, patch: UserUpdate): Promise<UserResponse> =>
    apiClient.patch(`/auth/users/${userId}`, patch),
};
