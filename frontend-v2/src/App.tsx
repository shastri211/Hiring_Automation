
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { AppRoutes } from './routes';
import { ThemeProvider } from './hooks/useTheme';
import { ConfirmProvider } from './hooks/useConfirm';
import { AuthProvider } from './hooks/useAuth';
import './styles/global.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5 * 60 * 1000, // 5 minutes
    },
  },
});

function App() {
  return (
    // AuthProvider is outermost - simplest option, since nothing else in the
    // tree needs to exist before auth state does (RequireAuth/Login consume
    // it via context regardless of nesting depth).
    <AuthProvider>
      <ThemeProvider>
        <QueryClientProvider client={queryClient}>
          <ConfirmProvider>
            <AppRoutes />
            <Toaster position="top-right" richColors closeButton />
          </ConfirmProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
