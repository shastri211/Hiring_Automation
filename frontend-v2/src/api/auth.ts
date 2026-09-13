import { apiClient } from './client';
import type { LoginRequest, UserCreate, UserResponse } from '../types';

export const authApi = {
  login: (payload: LoginRequest): Promise<UserResponse> => apiClient.post('/auth/login', payload),

  logout: (): Promise<{ success: boolean }> => apiClient.post('/auth/logout'),

  getMe: (): Promise<UserResponse> => apiClient.get('/auth/me'),

  createUser: (payload: UserCreate): Promise<UserResponse> => apiClient.post('/auth/users', payload),

  listUsers: (): Promise<UserResponse[]> => apiClient.get('/auth/users'),
};
