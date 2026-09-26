import { QueryClient } from '@tanstack/react-query';

// Module-level so AuthProvider can clear every cached query whenever the
// logged-in identity changes (login, logout, session expiry). Cached data is
// organization-scoped - without this, a second user logging in on the same
// tab would briefly see the previous user's organization's data.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});
