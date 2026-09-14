import { useCandidateEmails } from '../../hooks/useEmails';
import { Loader2, Mail, CheckCircle2, Clock, XCircle, ShieldOff } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

export const OutreachHistory = ({ resumeId }: { resumeId: number }) => {
  const { data: emails, isLoading } = useCandidateEmails(resumeId);

  if (isLoading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-6 flex justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!emails || emails.length === 0) {
    return null; // Don't show anything if there's no history
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6" id="outreach">
      <h2 className="text-lg font-semibold text-slate-900 mb-6 flex items-center gap-2">
        <Mail className="w-5 h-5 text-blue-600" /> Outreach History
      </h2>

      <div className="space-y-4 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-300 before:to-transparent">
        {emails.map((email) => (
          <div key={email.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
            <div className="flex items-center justify-center w-10 h-10 rounded-full border border-white bg-slate-100 text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 z-10">
              {email.status === 'SENT' ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> :
               email.status === 'PENDING' ? <Clock className="w-5 h-5 text-amber-500" /> :
               email.status === 'BLOCKED' ? <ShieldOff className="w-5 h-5 text-slate-400" /> :
               <XCircle className="w-5 h-5 text-rose-500" />}
            </div>
            
            <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-white p-4 rounded border border-slate-200 shadow-sm">
              <div className="flex justify-between items-start mb-1">
                <div className="font-semibold text-slate-800 text-sm">{email.subject}</div>
                <div className="text-xs text-slate-400 whitespace-nowrap ml-2">
                  {formatDistanceToNow(new Date(email.created_at), { addSuffix: true })}
                </div>
              </div>
              <div className="text-xs text-slate-500 bg-slate-50 p-2 rounded border border-slate-100 whitespace-pre-wrap mt-2 overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical' }}>
                {email.body_content}
              </div>
              {email.error_message && (
                <div className={`text-xs mt-2 p-2 rounded ${email.status === 'BLOCKED' ? 'text-slate-600 bg-slate-100' : 'text-rose-600 bg-rose-50'}`}>
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
