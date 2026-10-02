import type { ReactNode } from 'react';
import { ThemeToggle } from './ThemeToggle';
import { cn } from '../../utils/cn';

/**
 * Shared "no app chrome" shell for every page that lives outside
 * RequireAuth/AppLayout: sign-in and account recovery, the public apply page and
 * the candidate-facing interview room. It carries the same brand mark, surface,
 * hairline border and radius as the product itself (no shadow, no gradient), and
 * the theme toggle, so a candidate or a recruiter on a logged-out page is
 * clearly in the same system - and dark mode works there too.
 */
export const PublicPageShell = ({
  children,
  footer = 'Having trouble? Contact the recruiter who sent you this link.',
  wide = false,
}: {
  children: ReactNode;
  footer?: ReactNode;
  /** A wider column for content-heavy pages (the apply form). */
  wide?: boolean;
}) => (
  <div className="relative flex min-h-screen flex-col items-center justify-center bg-[var(--bg-app)] px-4 py-12">
    <div className="absolute right-4 top-4">
      <ThemeToggle />
    </div>
    <main className={cn('w-full', wide ? 'max-w-xl' : 'max-w-md')}>
      <div className="mb-6 flex items-center justify-center gap-2.5">
        <span
          aria-hidden="true"
          className="flex h-6 w-6 items-center justify-center rounded bg-[var(--accent)] text-[13px] font-bold text-[var(--accent-fg)]"
        >
          R
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">RecruitPro</span>
      </div>
      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)] p-6 sm:p-8">{children}</div>
      {footer && <p className="text-caption mt-4 text-center">{footer}</p>}
    </main>
  </div>
);
