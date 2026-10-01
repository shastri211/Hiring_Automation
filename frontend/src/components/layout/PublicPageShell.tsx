import { Briefcase } from 'lucide-react';

// Shared "no app chrome" shell for public-facing pages that live outside
// RequireAuth/AppLayout: the candidate-facing InterviewRoom and the HR Login
// page both need the same centered-card treatment with no sidebar/header.
// Extracted here (rather than duplicated) since both now need it and any
// future public page should look consistent with these two automatically.
export const PublicPageShell = ({
  children,
  footer = 'Having trouble? Contact the recruiter who sent you this link.',
}: {
  children: React.ReactNode;
  footer?: React.ReactNode;
}) => (
  <div className="min-h-screen flex flex-col items-center justify-center bg-[var(--bg-app)] px-4 py-12">
    <div className="w-full max-w-lg">
      <div className="flex items-center justify-center gap-2 mb-6 text-[var(--color-primary-700)] font-bold text-lg">
        <Briefcase size={22} />
        <span>RecruitPro</span>
      </div>
      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm p-8">
        {children}
      </div>
      {footer && <p className="text-center text-xs text-[var(--text-tertiary)] mt-4">{footer}</p>}
    </div>
  </div>
);
