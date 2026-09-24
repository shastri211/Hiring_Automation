import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { authApi } from '../api/auth';
import { registerPasswordChangeRequiredHandler, registerUnauthorizedHandler } from '../api/authEvents';
import { queryClient } from '../api/queryClient';
import type { MeResponse } from '../types';

interface AuthContextValue {
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

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Every cached query is organization-scoped data - drop it whenever the
  // session identity changes so nothing from a previous user (possibly of
  // another organization) is ever rendered.
  const resetSession = useCallback((next: MeResponse | null) => {
    queryClient.clear();
    setUser(next);
  }, []);

  // Establish whether a session already exists (e.g. page refresh with a
  // still-valid cookie). Any failure - 401 "not authenticated" is the
  // expected case for a logged-out visitor, but network errors etc. are
  // treated the same way - just means "not logged in", never a crash.
  useEffect(() => {
    let cancelled = false;
    authApi.getMe()
      .then((me) => { if (!cancelled) setUser(me); })
      .catch(() => { if (!cancelled) setUser(null); })
      .finally(() => { if (!cancelled) setIsLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      setUser(await authApi.getMe());
    } catch {
      resetSession(null);
    }
  }, [resetSession]);

  // React to a mid-session 401 (cookie expired/revoked while the app was
  // open) reported by client.ts's response interceptor: clear the user so
  // RequireAuth redirects to /login. A 403 password_change_required means
  // the account must replace its temporary password first - re-read the
  // session so RequireAuth routes to /change-password.
  useEffect(() => {
    registerUnauthorizedHandler(() => resetSession(null));
    registerPasswordChangeRequiredHandler(() => { void refreshMe(); });
    return () => {
      registerUnauthorizedHandler(null);
      registerPasswordChangeRequiredHandler(null);
    };
  }, [resetSession, refreshMe]);

  const login = useCallback(async (email: string, password: string) => {
    const me = await authApi.login({ email, password });
    resetSession(me);
    return me;
  }, [resetSession]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      resetSession(null);
    }
  }, [resetSession]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAdmin: user?.role === 'admin',
        isPlatformAdmin: !!user?.is_platform_admin,
        login,
        logout,
        refreshMe,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
