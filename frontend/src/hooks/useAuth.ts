import { createContext, useContext } from 'react';
import type { MeResponse } from '../types';

export interface AuthContextValue {
  /** The logged-in user with their organization, role and account flags. */
  user: MeResponse | null;
  isLoading: boolean;
  isAdmin: boolean;
  isPlatformAdmin: boolean;
  login: (email: string, password: string) => Promise<MeResponse>;
  logout: () => Promise<void>;
  /** Re-read /auth/me (e.g. after changing a temporary password). */
  refreshMe: () => Promise<void>;
}

// Provided by components/providers/AuthProvider.
export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
