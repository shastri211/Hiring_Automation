import { useCandidateEmails } from '../../hooks/useEmails';
import { Loader2, Mail, CheckCircle2, Clock, XCircle, ShieldOff } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export const OutreachHistory = ({ resumeId }: { resumeId: number }) => {
  const { data: emails, isLoading } = useCandidateEmails(resumeId);

  if (isLoading) {
    return (
      <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] p-6 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--color-info-icon)]" />
      </div>
    );
  }

  if (!emails || emails.length === 0) {
    return null; // Don't show anything if there's no history
  }

  return (
    <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] shadow-sm p-6" id="outreach">
      <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-6 flex items-center gap-2">
        <Mail className="w-5 h-5 text-[var(--color-info-icon)]" /> Outreach History
      </h2>

      <div className="space-y-4 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-[var(--border-strong)] before:to-transparent">
        {emails.map((email) => (
          <div key={email.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
            <div className="flex items-center justify-center w-10 h-10 rounded-full border border-[var(--bg-surface)] bg-[var(--bg-hover)] text-[var(--text-secondary)] shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
              {email.status === 'SENT' ? <CheckCircle2 className="w-5 h-5 text-[var(--color-success-500)]" /> :
               email.status === 'PENDING' ? <Clock className="w-5 h-5 text-[var(--color-warning-500)]" /> :
               email.status === 'BLOCKED' ? <ShieldOff className="w-5 h-5 text-[var(--text-tertiary)]" /> :
               <XCircle className="w-5 h-5 text-[var(--color-danger-500)]" />}
            </div>

            <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-[var(--bg-surface)] p-4 rounded border border-[var(--border-light)] shadow-sm">
              <div className="flex justify-between items-start mb-1">
                <div className="font-semibold text-[var(--text-primary)] text-sm">{email.subject}</div>
                <div className="text-xs text-[var(--text-tertiary)] whitespace-nowrap ml-2">
                  {formatDistanceToNow(new Date(email.created_at), { addSuffix: true })}
                </div>
              </div>
              <div className="text-xs text-[var(--text-secondary)] bg-[var(--bg-app)] p-2 rounded border border-[var(--border-light)] whitespace-pre-wrap mt-2 overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                {email.body_content}
              </div>
              {email.error_message && (
                <div className={`text-xs mt-2 p-2 rounded ${email.status === 'BLOCKED' ? 'text-[var(--text-secondary)] bg-[var(--bg-hover)]' : 'text-[var(--color-danger-subtle-text)] bg-[var(--color-danger-subtle-bg)]'}`}>
                  {email.status === 'BLOCKED' ? 'Blocked: ' : 'Failed: '}{email.error_message}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
