import { createBrowserRouter, RouterProvider, isRouteErrorResponse, useRouteError } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { Dashboard } from '../pages/Dashboard';
import { JobsList } from '../pages/JobsList';
import { Candidate360 } from '../pages/Candidate360';
import { InterviewWorkspace } from '../pages/InterviewWorkspace';
import { Shortlisted } from '../pages/Shortlisted';
import { JobWizard } from '../pages/JobWizard';
import { JobWorkspace } from '../pages/JobWorkspace';
import { JobUpload } from '../pages/JobUpload';
import { JobProcessing } from '../pages/JobProcessing';
import { JobCandidates } from '../pages/JobCandidates';
import { GlobalCandidates } from '../pages/GlobalCandidates';
import { GlobalInterviews } from '../pages/GlobalInterviews';
import { TalentPool } from '../pages/TalentPool';
import { Outreach } from '../pages/Outreach';
import { AIScreening } from '../pages/AIScreening';
import { InterviewAnalysis } from '../pages/InterviewAnalysis';
import { Analytics } from '../pages/Analytics';
import { Integrations } from '../pages/Integrations';
import { Settings } from '../pages/Settings';
import { EmailTemplates } from '../pages/EmailTemplates';
import { InterviewRoom } from '../pages/InterviewRoom';

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
    element: <AppLayout />,
    errorElement: <RouteError />,
    children: [
      {
        index: true,
        element: <Dashboard />
      },
      // RECRUITING
      {
        path: 'jobs',
        element: <JobsList />
      },
      {
        path: 'jobs/new',
        element: <JobWizard />
      },
      {
        path: 'jobs/:id',
        element: <JobWorkspace />
      },
      {
        path: 'jobs/:id/upload',
        element: <JobUpload />
      },
      {
        path: 'jobs/:id/processing',
        element: <JobProcessing />
      },
      {
        path: 'jobs/:id/candidates',
        element: <JobCandidates />
      },
      {
        path: 'jobs/:id/candidates/:resumeId',
        element: <Candidate360 />
      },
      {
        path: 'candidates',
        element: <GlobalCandidates />
      },
      {
        path: 'shortlisted',
        element: <Shortlisted />
      },
      {
        path: 'interviews',
        element: <GlobalInterviews />
      },
      {
        path: 'interview/:jobId/:resumeId',
        element: <InterviewWorkspace />
      },
      {
        path: 'talent-pool',
        element: <TalentPool />
      },
      
      // COMMUNICATION
      {
        path: 'outreach',
        element: <Outreach />
      },
      {
        path: 'templates',
        element: <EmailTemplates />
      },

      // INTELLIGENCE
      {
        path: 'ai-screening',
        element: <AIScreening />
      },
      {
        path: 'interview-analysis',
        element: <InterviewAnalysis />
      },
      {
        path: 'analytics',
        element: <Analytics />
      },

      // SYSTEM
      {
        path: 'integrations',
        element: <Integrations />
      },
      {
        path: 'settings',
        element: <Settings />
      }
    ]
  },
  // Public, unauthenticated candidate-facing route - deliberately a sibling of
  // the AppLayout root, not a child, since it has no sidebar/header chrome.
  {
    path: '/interview-room/:token',
    element: <InterviewRoom />,
    errorElement: <RouteError />
  }
]);

export const AppRoutes = () => {
  return <RouterProvider router={router} />;
};
