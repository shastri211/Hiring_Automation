
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './api/queryClient';
import { Toaster } from 'sonner';
import { AppRoutes } from './routes';
import { ThemeProvider } from './hooks/useTheme';
import { ConfirmProvider } from './hooks/useConfirm';
import { AuthProvider } from './hooks/useAuth';
import './styles/global.css';


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
