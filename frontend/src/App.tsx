
import { QueryClientProvider } from '@tanstack/react-query';
import { queryClient } from './api/queryClient';
import { AppRoutes } from './routes';
import { ThemeProvider } from './components/providers/ThemeProvider';
import { Toaster } from './components/ui/Toaster';
import { ConfirmProvider } from './components/providers/ConfirmProvider';
import { AuthProvider } from './components/providers/AuthProvider';
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
            <Toaster />
          </ConfirmProvider>
        </QueryClientProvider>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
