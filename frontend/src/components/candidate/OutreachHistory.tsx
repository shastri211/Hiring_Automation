import { formatDistanceToNow } from 'date-fns';
import { Mail } from 'lucide-react';
import { useCandidateEmails } from '../../hooks/useEmails';
import { Section, Skeleton, StatusDot } from '../ui';
import { emailStatusLabel, getEmailStatusBadgeVariant } from '../../utils/status';

/**
 * Outreach history for one candidate: each email's subject, status, time and a
 * body preview, in the order the API returns them. Renders nothing when there
 * is no history (callers show their own empty context).
 */
export const OutreachHistory = ({ resumeId }: { resumeId: number }) => {
  const { data: emails, isLoading } = useCandidateEmails(resumeId);

  if (isLoading) {
    return (
      <Section title="Outreach" icon={<Mail size={13} />}>
        <div className="space-y-3" aria-hidden="true">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-12 w-full" />
        </div>
      </Section>
    );
  }

  if (!emails || emails.length === 0) return null;

  return (
    <Section title="Outreach" icon={<Mail size={13} />} id="outreach">
      <ul className="divide-y divide-[var(--border-light)]">
        {emails.map((email) => (
          <li key={email.id} className="py-3 first:pt-0 last:pb-0">
            <div className="flex items-start justify-between gap-3">
              <p className="min-w-0 text-sm font-medium text-[var(--text-primary)]">{email.subject}</p>
              <time dateTime={email.created_at} className="text-caption shrink-0 whitespace-nowrap">
                {formatDistanceToNow(new Date(email.created_at), { addSuffix: true })}
              </time>
            </div>
            <StatusDot variant={getEmailStatusBadgeVariant(email.status)} className="mt-1 text-xs text-[var(--text-secondary)]">
              {emailStatusLabel(email.status)}
            </StatusDot>
            <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-[var(--text-secondary)]">{email.body_content}</p>
            {email.error_message && (
              <p className={`mt-2 text-xs ${email.status === 'FAILED' ? 'text-[var(--color-danger-subtle-text)]' : 'text-[var(--text-secondary)]'}`}>
                {email.status === 'BLOCKED' ? 'Blocked: ' : email.status === 'FAILED' ? 'Failed: ' : ''}{email.error_message}
              </p>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
};
