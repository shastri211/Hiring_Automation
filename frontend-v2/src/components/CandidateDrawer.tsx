import { useState, useEffect } from 'react';
import { Mail, Phone, ExternalLink, ChevronRight, Save } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { resumesApi } from '../api/resumes';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation } from '../hooks/useDecisionMutation';
import { Button } from './ui/Button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from './ui';
import { 
  ScoreVisualizer, 
  DecisionControlBar, 
  ExtractedSkills, 
  ScreeningAnalysis,
  CandidateStatusBanner,
} from './candidate/CandidateComponents';

interface CandidateDrawerProps {
  jobId: number;
  resumeId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onView360?: () => void;
}

export const CandidateDrawer = ({ jobId, resumeId, isOpen, onClose, onView360 }: CandidateDrawerProps) => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId!),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId!),
    enabled: isOpen && resumeId !== null,
  });

  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJob(jobId),
    enabled: isOpen,
  });

  const decisionMutation = useDecisionMutation(jobId);

  const [localNotes, setLocalNotes] = useState('');

  // Reset immediately on resumeId change (before the new query resolves) so
  // a candidate with no screening/notes never inherits the PREVIOUS
  // candidate's still-in-state text - which the disabled-check below would
  // then treat as a real edit and let Save Notes write onto the wrong resume.
  useEffect(() => {
    setLocalNotes('');
  }, [resumeId]);

  useEffect(() => {
    if (data?.screening?.notes !== undefined) {
      setLocalNotes(data.screening.notes || '');
    }
  }, [data?.screening?.notes]);

  const handleSaveNotes = () => {
    if (resumeId !== null) {
      decisionMutation.mutate({ resumeId, decision: data?.screening?.decision || null, notes: localNotes });
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="left-auto right-0 top-0 h-dvh w-full max-w-xl translate-x-0 translate-y-0 gap-0 overflow-hidden rounded-none border-y-0 border-r-0 p-0 shadow-2xl sm:rounded-none">
      <div className="relative flex h-full w-full max-w-xl flex-col overflow-hidden bg-[var(--bg-surface)]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-light)] bg-[var(--bg-surface)]">
          <div>
            <DialogTitle className="text-lg font-semibold text-[var(--text-primary)]">
              {isLoading ? 'Loading...' : data?.profile?.name || `Candidate #${resumeId}`}
            </DialogTitle>
            <DialogDescription className="mt-0.5 text-xs font-medium text-[var(--text-secondary)]">
              {job?.title ? `Applying for ${job.title}` : 'Candidate application'}
              {data?.filename && <> &bull; {data.filename}</>}
            </DialogDescription>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-[var(--bg-app)]">
          {isLoading && (
            <div className="flex justify-center py-20">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary-500)]"></div>
            </div>
          )}

          {isError && (
            <div className="bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)] p-4 rounded-lg flex items-center justify-between gap-4">
              <span>Failed to load candidate details.</span>
              <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
            </div>
          )}

          {data && (
            <div className="space-y-6">
              {/* Status banner when no screening result or PRE_SCREENED_OUT */}
              {(!data.screening || data.screening.decision === 'PRE_SCREENED_OUT') && (
                <CandidateStatusBanner
                  resumeStatus={data.screening?.status ?? null}
                  decision={data.screening?.decision ?? null}
                  errorMessage={data.screening?.error_message ?? null}
                />
              )}

              {/* Score only when an actual score exists (not PRE_SCREENED_OUT) */}
              {data.screening && data.screening.decision !== 'PRE_SCREENED_OUT' && (
                <ScoreVisualizer screening={data.screening} />
              )}

              {/* Profile Details */}
              <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-[var(--border-light)] bg-[var(--bg-app)]">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">Candidate Profile</h3>
                </div>
                <div className="p-5 space-y-4 text-sm">
                  <DecisionControlBar
                    decision={data.screening?.decision}
                    isPending={decisionMutation.isPending}
                    onDecision={(d) => {
                      if (resumeId !== null) decisionMutation.mutate({ resumeId, decision: d, notes: localNotes });
                    }}
                  />

                  <div className="mt-4 pt-4 border-t border-[var(--border-light)]">
                    <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">Recruiter Notes</label>
                    <textarea
                      className="w-full bg-[var(--bg-surface)] text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] border-[var(--border-light)] rounded-md shadow-sm focus:border-[var(--border-focus)] focus:ring-[var(--border-focus)] sm:text-sm p-3"
                      rows={3}
                      placeholder="Add private notes about this candidate..."
                      value={localNotes}
                      onChange={(e) => setLocalNotes(e.target.value)}
                    />
                    <div className="flex justify-end mt-2">
                      <Button variant="secondary" size="sm" onClick={handleSaveNotes} disabled={decisionMutation.isPending || localNotes === (data.screening?.notes || '')}>
                        <Save className="w-4 h-4 mr-2" /> Save Notes
                      </Button>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-2">
                    <div className="flex gap-3">
                      <Mail className="w-4 h-4 text-[var(--text-tertiary)] mt-0.5" />
                      <span className="text-[var(--text-secondary)] break-all">{data.profile?.email || '—'}</span>
                    </div>
                    <div className="flex gap-3">
                      <Phone className="w-4 h-4 text-[var(--text-tertiary)] mt-0.5" />
                      <span className="text-[var(--text-secondary)]">{data.profile?.phone || '—'}</span>
                    </div>
                  </div>
                  
                  <ExtractedSkills profile={data.profile} />
                </div>
              </div>

              {data.screening && data.screening.decision !== 'PRE_SCREENED_OUT' && (
                <ScreeningAnalysis screening={data.screening} />
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-[var(--border-light)] bg-[var(--bg-surface)] flex justify-between items-center">
          {data?.filename ? (
            <a
              href={resumesApi.getResumeFileUrl(resumeId ?? 0)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)] font-medium flex items-center gap-1 focus-ring rounded px-1"
            >
              <ExternalLink className="w-4 h-4" /> Original Resume
            </a>
          ) : (
            <span className="text-sm text-[var(--text-tertiary)] font-medium flex items-center gap-1 px-1 cursor-not-allowed" title="Original resume unavailable">
              <ExternalLink className="w-4 h-4 opacity-50" /> Original Resume Unavailable
            </span>
          )}
          <Button 
            onClick={() => {
              if (onView360) onView360();
            }}
          >
            View Full Profile <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </div>
      </DialogContent>
    </Dialog>
  );
};
