import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Mic, Clock, FileText, PlayCircle, BarChart3, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { Button } from '../components/ui/Button';
import type { IntegrationResponse } from '../types';
import { toast } from 'sonner';

export const InterviewWorkspace = () => {
  const { id: jobIdStr, resumeId: resumeIdStr } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const jobId = parseInt(jobIdStr || '0', 10);
  const resumeId = parseInt(resumeIdStr || '0', 10);

  const [triggerResponse, setTriggerResponse] = useState<IntegrationResponse | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const { data: candidate, isLoading: isLoadingCandidate } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId),
    enabled: !!jobId && !!resumeId,
  });

  const triggerMutation = useMutation({
    mutationFn: () => api.integration.triggerInterview(jobId, resumeId),
    onSuccess: (data) => {
      setTriggerResponse(data);
      setTriggerError(null);
      toast.success(data.message || 'Interview request sent.');
    },
    onError: (err: any) => {
      setTriggerError(err.message || 'Failed to trigger interview');
      setTriggerResponse(null);
      toast.error(err.message || 'Failed to trigger interview');
    }
  });

  const handleBack = () => {
    // Navigate back to Candidate 360 with context
    navigate(`/jobs/${jobId}/candidates/${resumeId}`, { state: location.state });
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 shrink-0 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button 
            onClick={handleBack}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-xl font-bold text-slate-900 flex items-center gap-3">
              Interview Workspace
              <span className="bg-slate-100 text-slate-600 text-xs px-2.5 py-1 rounded-full font-medium border border-slate-200">
                Extension Point
              </span>
            </h1>
            <p className="text-sm text-slate-500">
              {isLoadingCandidate ? 'Loading candidate...' : candidate?.profile?.name || `Candidate #${resumeId}`} &bull; Job #{jobId}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button 
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
            className="bg-purple-600 hover:bg-purple-700 text-white border-transparent"
          >
            {triggerMutation.isPending ? 'Triggering...' : (
              <><Mic className="w-4 h-4 mr-2" /> Trigger Voice Interview</>
            )}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto space-y-6">
          
          {/* Mutation Status Banner */}
          {triggerResponse && (
            <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5" />
              <div>
                <h4 className="font-medium">Trigger Successful</h4>
                <p className="text-sm mt-1 text-green-700">API Response: {triggerResponse.message}</p>
              </div>
            </div>
          )}

          {triggerError && (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
              <div>
                <h4 className="font-medium">Trigger Failed</h4>
                <p className="text-sm mt-1 text-red-700">{triggerError}</p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            
            {/* Timeline */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 col-span-1">
              <h3 className="text-sm font-semibold text-slate-900 mb-6 flex items-center gap-2">
                <Clock className="w-4 h-4 text-slate-400" /> Lifecycle Status
              </h3>
              <div className="text-center py-10 px-4">
                <div className="bg-slate-50 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
                  <Clock className="w-6 h-6 text-slate-300" />
                </div>
                <h4 className="text-sm font-medium text-slate-900 mb-1">
                  {candidate?.interview?.status || 'No Interview Scheduled'}
                </h4>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {candidate?.interview?.status ? 'Interview status synced from the integration platform.' : 'Trigger an interview to begin the process.'}
                </p>
              </div>
            </div>

            {/* Audio / Evaluation */}
            <div className="col-span-1 md:col-span-2 space-y-6">
              
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <PlayCircle className="w-4 h-4 text-slate-400" /> Recording & Transcript
                </h3>
                {candidate?.interview?.transcript ? (
                  <div className="bg-slate-50 p-4 rounded-lg text-sm text-slate-700 whitespace-pre-wrap font-mono">
                    {candidate.interview.transcript}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 px-4 border-2 border-dashed border-slate-100 rounded-lg bg-slate-50/50">
                    <FileText className="w-8 h-8 text-slate-300 mb-3" />
                    <h4 className="text-sm font-medium text-slate-700 mb-1">No Transcript Available</h4>
                    <p className="text-xs text-slate-500 max-w-sm text-center">
                      Future voice-agent integrations will stream real-time transcripts and audio playback here.
                    </p>
                  </div>
                )}
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-slate-400" /> Interview Evaluation
                </h3>
                {candidate?.interview?.evaluation ? (
                  <div className="bg-slate-50 p-4 rounded-lg text-sm text-slate-700">
                    <pre className="whitespace-pre-wrap font-mono text-xs">
                      {JSON.stringify(candidate.interview.evaluation, null, 2)}
                    </pre>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 px-4 border-2 border-dashed border-slate-100 rounded-lg bg-slate-50/50">
                    <BarChart3 className="w-8 h-8 text-slate-300 mb-3" />
                    <h4 className="text-sm font-medium text-slate-700 mb-1">No Evaluation Available</h4>
                    <p className="text-xs text-slate-500 max-w-sm text-center">
                      AI evaluation results and scoring will appear here once the interview completes.
                    </p>
                  </div>
                )}
              </div>

            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
