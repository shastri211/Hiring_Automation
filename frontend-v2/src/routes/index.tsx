import type { ComponentType } from 'react';
import { createBrowserRouter, RouterProvider, isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { Login } from '../pages/Login';
import { RequireAuth } from '../components/auth/RequireAuth';
import { RequirePlatformAdmin } from '../components/auth/RequirePlatformAdmin';
import { Spinner } from '../components/ui';

// Each page is its own chunk, fetched on first navigation to it, so the
// initial bundle carries only the app shell (and e.g. recharts loads only
// with the pages that chart).
const page = <K extends string>(load: () => Promise<Record<K, ComponentType>>, name: K) =>
  async () => ({ Component: (await load())[name] });

// Shown while the first matched page's chunk loads on a fresh visit.
const PageLoading = () => (
  <div className="flex min-h-screen items-center justify-center">
    <Spinner size={32} />
  </div>
);

const RouteError = () => {
  const error = useRouteError();
  const detail = isRouteErrorResponse(error) ? error.statusText : 'The page could not be displayed.';

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6">
      <section className="max-w-md rounded-xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm font-semibold uppercase tracking-wide text-[var(--color-primary-600)]">Something went wrong</p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-900">We could not load this page</h1>
        <p className="mt-3 text-sm leading-6 text-slate-500">{detail}</p>
        <a className="focus-ring mt-6 inline-flex rounded-md bg-[var(--color-primary-600)] px-4 py-2 text-sm font-medium text-white hover:bg-[var(--color-primary-700)]" href="/">
          Return to dashboard
        </a>
      </section>
    </main>
  );
};

const router = createBrowserRouter([
  {
    path: '/',
    // RequireAuth sits above AppLayout so every route under it needs a valid
    // HR session; the existing `children` array (and AppLayout itself) is
    // unchanged - RequireAuth just renders it via <Outlet /> once a user is
    // confirmed.
    element: <RequireAuth />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />,
    children: [
      // Authenticated but outside AppLayout: while an admin-issued temporary
      // password is still in place, RequireAuth sends the user here and every
      // other API call is refused, so the app chrome couldn't load.
      {
        path: 'change-password',
        lazy: page(() => import('../pages/ChangePassword'), 'ChangePassword')
      },
      {
        element: <AppLayout />,
        children: [
          {
            index: true,
            lazy: page(() => import('../pages/Dashboard'), 'Dashboard')
          },
          // RECRUITING
          {
            path: 'jobs',
            lazy: page(() => import('../pages/JobsList'), 'JobsList')
          },
          {
            path: 'jobs/new',
            lazy: page(() => import('../pages/JobWizard'), 'JobWizard')
          },
          {
            path: 'jobs/:id',
            lazy: page(() => import('../pages/JobWorkspace'), 'JobWorkspace')
          },
          {
            path: 'jobs/:id/upload',
            lazy: page(() => import('../pages/JobUpload'), 'JobUpload')
          },
          {
            path: 'jobs/:id/processing',
            lazy: page(() => import('../pages/JobProcessing'), 'JobProcessing')
          },
          {
            path: 'jobs/:id/candidates',
            lazy: page(() => import('../pages/JobCandidates'), 'JobCandidates')
          },
          {
            path: 'processing',
            lazy: page(() => import('../pages/Processing'), 'Processing')
          },
          {
            path: 'jobs/:id/candidates/:resumeId',
            lazy: page(() => import('../pages/Candidate360'), 'Candidate360')
          },
          {
            path: 'candidates',
            lazy: page(() => import('../pages/GlobalCandidates'), 'GlobalCandidates')
          },
          {
            path: 'candidates/duplicates',
            lazy: page(() => import('../pages/MatchSuggestions'), 'MatchSuggestions')
          },
          {
            path: 'shortlisted',
            lazy: page(() => import('../pages/Shortlisted'), 'Shortlisted')
          },
          {
            path: 'interviews',
            lazy: page(() => import('../pages/GlobalInterviews'), 'GlobalInterviews')
          },
          {
            path: 'interview/:jobId/:resumeId',
            lazy: page(() => import('../pages/InterviewWorkspace'), 'InterviewWorkspace')
          },
          {
            path: 'talent-pool',
            lazy: page(() => import('../pages/TalentPool'), 'TalentPool')
          },

          // COMMUNICATION
          {
            path: 'outreach',
            lazy: page(() => import('../pages/Outreach'), 'Outreach')
          },
          {
            path: 'templates',
            lazy: page(() => import('../pages/EmailTemplates'), 'EmailTemplates')
          },

          // INTELLIGENCE
          {
            path: 'ai-screening',
            lazy: page(() => import('../pages/AIScreening'), 'AIScreening')
          },
          {
            path: 'interview-analysis',
            lazy: page(() => import('../pages/InterviewAnalysis'), 'InterviewAnalysis')
          },
          {
            path: 'analytics',
            lazy: page(() => import('../pages/Analytics'), 'Analytics')
          },

          // SYSTEM
          {
            path: 'integrations',
            // Platform-level (shared provider configuration) - platform
            // admins only; everyone else sees a "not available" state.
            lazy: async () => {
              const { Integrations } = await import('../pages/Integrations');
              return { element: <RequirePlatformAdmin><Integrations /></RequirePlatformAdmin> };
            }
          },
          {
            path: 'settings',
            lazy: page(() => import('../pages/Settings'), 'Settings')
          }
        ]
      }
    ]
  },
  // Public, unauthenticated candidate-facing route - deliberately a sibling of
  // the RequireAuth root, not a child, since it has no sidebar/header chrome
  // and must never be gated by HR auth.
  {
    path: '/interview-room/:token',
    lazy: page(() => import('../pages/InterviewRoom'), 'InterviewRoom'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  // Public candidate apply page - same sibling-of-RequireAuth placement as
  // the interview room; auth is possession of the job's application token.
  {
    path: '/apply/:token',
    lazy: page(() => import('../pages/ApplyPage'), 'ApplyPage'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  // Public HR login page - also a sibling of the RequireAuth root, since it
  // must be reachable by a logged-out visitor.
  {
    path: '/login',
    element: <Login />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  // Public self-service company signup and its email-verification landing.
  {
    path: '/signup',
    lazy: page(() => import('../pages/Signup'), 'Signup'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  {
    path: '/verify-email',
    lazy: page(() => import('../pages/VerifyEmail'), 'VerifyEmail'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  // Public forgotten-password request and the emailed reset-link landing.
  {
    path: '/forgot-password',
    lazy: page(() => import('../pages/ForgotPassword'), 'ForgotPassword'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  },
  {
    path: '/reset-password',
    lazy: page(() => import('../pages/ResetPassword'), 'ResetPassword'),
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />
  }
]);

export const AppRoutes = () => {
  return <RouterProvider router={router} />;
};
