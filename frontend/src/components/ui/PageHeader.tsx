import type { ReactNode } from 'react';
import { cn } from '../../utils/cn';

/**
 * PageHeader — the title + subtitle + right-aligned-actions row repeated
 * near-identically at the top of Dashboard, JobsList, JobWorkspace,
 * JobCandidates, Shortlisted and InterviewWorkspace. Centralizing it fixes
 * any drift between pages (heading level, spacing, type scale) for free.
 */
export interface PageHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  /** Optional leading element (e.g. a back button) rendered inline before the title block. */
  leading?: ReactNode;
  /** Use a smaller title size for detail-view headers (Candidate 360, Interview Workspace) that sit in a compact bordered bar rather than a page's top-level heading. */
  size?: 'page' | 'section';
  className?: string;
}

export const PageHeader = ({ title, subtitle, actions, eyebrow, leading, size = 'page', className }: PageHeaderProps) => (
  <div className={cn('flex flex-wrap items-start justify-between gap-4', className)}>
    <div className="flex items-center gap-4 min-w-0">
      {leading}
      <div className="min-w-0">
        {eyebrow}
        <h1 className={size === 'page' ? 'text-page-title truncate' : 'text-section-heading truncate'}>{title}</h1>
        {subtitle && <p className="text-body mt-1">{subtitle}</p>}
      </div>
    </div>
    {actions && <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>}
  </div>
);
