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
  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId!),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId!),
    enabled: isOpen && resumeId !== null,
  });

  const decisionMutation = useDecisionMutation(jobId);

  const [localNotes, setLocalNotes] = useState('');
  
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
      <div className="relative flex h-full w-full max-w-xl flex-col overflow-hidden bg-white">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 bg-white">
          <div>
            <DialogTitle className="text-lg font-semibold text-slate-900">
              {isLoading ? 'Loading...' : data?.profile?.name || `Candidate #${resumeId}`}
            </DialogTitle>
            <DialogDescription className="mt-0.5 text-xs font-medium text-slate-500">
              Job #{jobId} &bull; Resume #{resumeId}
            </DialogDescription>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50">
          {isLoading && (
            <div className="flex justify-center py-20">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--color-primary-500)]"></div>
            </div>
          )}

          {isError && (
            <div className="bg-red-50 text-red-700 p-4 rounded-lg">
              Failed to load candidate details.
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
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b border-slate-100 bg-slate-50/50">
                  <h3 className="text-sm font-semibold text-slate-900">Candidate Profile</h3>
                </div>
                <div className="p-5 space-y-4 text-sm">
                  <DecisionControlBar 
                    decision={data.screening?.decision}
                    isPending={decisionMutation.isPending}
                    onDecision={(d) => {
                      if (resumeId !== null) decisionMutation.mutate({ resumeId, decision: d, notes: localNotes });
                    }}
                  />

                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <label className="block text-sm font-medium text-slate-700 mb-2">Recruiter Notes</label>
                    <textarea 
                      className="w-full border-slate-200 rounded-md shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm p-3"
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
                      <Mail className="w-4 h-4 text-slate-400 mt-0.5" />
                      <span className="text-slate-700 break-all">{data.profile?.email || '—'}</span>
                    </div>
                    <div className="flex gap-3">
                      <Phone className="w-4 h-4 text-slate-400 mt-0.5" />
                      <span className="text-slate-700">{data.profile?.phone || '—'}</span>
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
        <div className="p-4 border-t border-slate-200 bg-white flex justify-between items-center">
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
            <span className="text-sm text-slate-400 font-medium flex items-center gap-1 px-1 cursor-not-allowed" title="Original resume unavailable">
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
