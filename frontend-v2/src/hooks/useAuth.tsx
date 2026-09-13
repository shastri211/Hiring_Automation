import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { authApi } from '../api/auth';
import { registerUnauthorizedHandler } from '../api/authEvents';
import type { UserResponse } from '../types';

interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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

  // React to a mid-session 401 (cookie expired/revoked while the app was
  // open) reported by client.ts's response interceptor: clear the user so
  // RequireAuth redirects to /login.
  useEffect(() => {
    registerUnauthorizedHandler(() => setUser(null));
    return () => registerUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const me = await authApi.login({ email, password });
    setUser(me);
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
