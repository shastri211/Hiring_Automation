import { useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  ArrowLeft, Mic, Clock, FileText, PlayCircle, BarChart3, AlertCircle, CheckCircle2,
  Link as LinkIcon, Copy, RefreshCw, ExternalLink,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { jobsApi } from '../api/jobs';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { Button, Badge } from '../components/ui';
import { getInterviewStatusBadgeVariant } from '../utils/status';
import type { DograhEvaluationEnvelope, IntegrationResponse } from '../types';

const STEPS: { key: string; label: string }[] = [
  { key: 'PENDING', label: 'Requested' },
  { key: 'SCHEDULED', label: 'Link sent' },
  { key: 'IN_PROGRESS', label: 'In progress' },
  { key: 'COMPLETED', label: 'Completed' },
];

function parseMaybeJson(value: unknown): Record<string, unknown> | null {
  if (value == null) return null;
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return typeof parsed === 'object' ? parsed : null;
    } catch {
      return null;
    }
  }
  return typeof value === 'object' ? (value as Record<string, unknown>) : null;
}

function formatDuration(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

const LifecycleStepper = ({ status, scheduledAt, completedAt }: { status: string; scheduledAt?: string | null; completedAt?: string | null }) => {
  if (status === 'FAILED') {
    return (
      <div className="text-center py-8 px-4">
        <div className="bg-[var(--color-danger-subtle-bg)] w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
          <AlertCircle className="w-6 h-6 text-[var(--color-danger-600)]" />
        </div>
        <h4 className="text-sm font-medium text-slate-900 mb-1">Interview Failed</h4>
        <p className="text-xs text-slate-500 leading-relaxed">
          The interview could not be scheduled or completed. Try triggering it again.
        </p>
      </div>
    );
  }

  const currentIndex = Math.max(0, STEPS.findIndex((s) => s.key === status));

  return (
    <ol className="space-y-4">
      {STEPS.map((step, i) => {
        const done = i <= currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <li key={step.key} className="flex items-start gap-3">
            <span
              className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
                done
                  ? 'bg-[var(--color-primary-600)] text-white'
                  : 'bg-slate-100 text-slate-400 border border-slate-200'
              }`}
            >
              {done ? '✓' : i + 1}
            </span>
            <div>
              <p className={`text-sm font-medium ${isCurrent ? 'text-slate-900' : done ? 'text-slate-600' : 'text-slate-400'}`}>
                {step.label}
              </p>
              {step.key === 'SCHEDULED' && scheduledAt && (
                <p className="text-xs text-slate-400">{formatDistanceToNow(new Date(scheduledAt), { addSuffix: true })}</p>
              )}
              {step.key === 'COMPLETED' && completedAt && (
                <p className="text-xs text-slate-400">{formatDistanceToNow(new Date(completedAt), { addSuffix: true })}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
};

export const InterviewWorkspace = () => {
  const { id: jobIdStr, resumeId: resumeIdStr } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const jobId = parseInt(jobIdStr || '0', 10);
  const resumeId = parseInt(resumeIdStr || '0', 10);

  const [triggerResponse, setTriggerResponse] = useState<IntegrationResponse | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const { data: candidate, isLoading: isLoadingCandidate, error: candidateError } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId),
    enabled: !!jobId && !!resumeId,
  });

  const interview = candidate?.interview;

  const triggerMutation = useMutation({
    mutationFn: () => api.integration.triggerInterview(jobId, resumeId),
    onSuccess: (data) => {
      setTriggerResponse(data);
      setTriggerError(null);
      toast.success(data.message || 'Interview link created.');
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, resumeId) });
    },
    onError: (err: { message?: string }) => {
      setTriggerError(err.message || 'Failed to trigger interview');
      setTriggerResponse(null);
      toast.error(err.message || 'Failed to trigger interview');
    }
  });

  const resyncMutation = useMutation({
    mutationFn: () => jobsApi.resyncInterview(jobId, resumeId),
    onSuccess: (data) => {
      toast.success(data.message || 'Interview resynced.');
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, resumeId) });
    },
    onError: (err: { message?: string }) => toast.error(err.message || 'Failed to resync interview from Dograh.'),
  });

  const handleCopyLink = async () => {
    if (!interview?.interview_link) return;
    try {
      await navigator.clipboard.writeText(interview.interview_link);
      toast.success('Interview link copied to clipboard.');
    } catch {
      toast.error('Could not copy link. Copy it manually: ' + interview.interview_link);
    }
  };

  const handleBack = () => {
    navigate(`/jobs/${jobId}/candidates/${resumeId}`, { state: location.state });
  };

  const rawEvaluation = interview?.evaluation as DograhEvaluationEnvelope | Record<string, unknown> | undefined | null;
  const isDograhEvaluation = !!rawEvaluation && typeof rawEvaluation === 'object' && (rawEvaluation as DograhEvaluationEnvelope).source === 'dograh';
  const gatheredContext = isDograhEvaluation ? parseMaybeJson((rawEvaluation as DograhEvaluationEnvelope).gathered_context) : null;
  const costInfo = isDograhEvaluation ? parseMaybeJson((rawEvaluation as DograhEvaluationEnvelope).cost_info) : null;
  const callDuration = costInfo && typeof costInfo.call_duration_seconds === 'number' ? costInfo.call_duration_seconds : null;

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-50 overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b border-slate-200 px-8 py-4 shrink-0 flex items-center justify-between flex-wrap gap-3">
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
              {interview ? (
                <Badge variant={getInterviewStatusBadgeVariant(interview.status)}>{interview.status}</Badge>
              ) : (
                <Badge variant="neutral">Not scheduled</Badge>
              )}
            </h1>
            <p className="text-sm text-slate-500">
              {isLoadingCandidate ? 'Loading candidate...' : candidate?.profile?.name || `Candidate #${resumeId}`} &bull; Job #{jobId}
              {interview?.provider === 'dograh' && <span className="ml-2 text-xs text-slate-400">via Dograh</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {interview?.interview_link && (
            <Button variant="secondary" size="sm" onClick={handleCopyLink}>
              <Copy className="w-4 h-4 mr-1" /> Copy Interview Link
            </Button>
          )}
          {interview?.provider_run_id && interview.status !== 'COMPLETED' && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => resyncMutation.mutate()}
              disabled={resyncMutation.isPending}
            >
              <RefreshCw className={`w-4 h-4 mr-1 ${resyncMutation.isPending ? 'animate-spin' : ''}`} /> Resync
            </Button>
          )}
          <Button
            onClick={() => triggerMutation.mutate()}
            disabled={triggerMutation.isPending}
            className="bg-purple-600 hover:bg-purple-700 text-white border-transparent"
          >
            {triggerMutation.isPending ? 'Creating link...' : (
              <><Mic className="w-4 h-4 mr-2" /> {interview ? 'Resend Interview Link' : 'Create Interview Link'}</>
            )}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto space-y-6">

          {candidateError && (
            <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
              <div>
                <h4 className="font-medium">Could not load candidate</h4>
                <p className="text-sm mt-1 text-red-700">{(candidateError as { message?: string }).message || 'Please try again.'}</p>
              </div>
            </div>
          )}

          {/* Mutation Status Banner */}
          {triggerResponse && (
            <div className="bg-green-50 border border-green-200 text-green-800 rounded-lg p-4 flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5" />
              <div>
                <h4 className="font-medium">Interview Link Ready</h4>
                <p className="text-sm mt-1 text-green-700">{triggerResponse.message}</p>
                {interview?.interview_link && (
                  <p className="text-xs mt-2 text-green-700 break-all flex items-center gap-1">
                    <LinkIcon className="w-3 h-3 shrink-0" /> {interview.interview_link}
                  </p>
                )}
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
              {interview ? (
                <LifecycleStepper status={interview.status} scheduledAt={interview.scheduled_at} completedAt={interview.completed_at} />
              ) : (
                <div className="text-center py-10 px-4">
                  <div className="bg-slate-50 w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3">
                    <Clock className="w-6 h-6 text-slate-300" />
                  </div>
                  <h4 className="text-sm font-medium text-slate-900 mb-1">No Interview Scheduled</h4>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    Create an interview link to begin the process.
                  </p>
                </div>
              )}
            </div>

            {/* Audio / Evaluation */}
            <div className="col-span-1 md:col-span-2 space-y-6">

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <PlayCircle className="w-4 h-4 text-slate-400" /> Recording &amp; Transcript
                </h3>
                {interview?.recording_url || interview?.transcript_url || interview?.transcript ? (
                  <div className="space-y-3">
                    {interview.recording_url && (
                      <audio controls className="w-full" src={interview.recording_url}>
                        Your browser does not support audio playback.
                      </audio>
                    )}
                    {interview.transcript_url && (
                      <a
                        href={interview.transcript_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1.5 text-sm text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)] font-medium"
                      >
                        <ExternalLink className="w-3.5 h-3.5" /> View full transcript
                      </a>
                    )}
                    {!interview.transcript_url && interview.transcript && (
                      <div className="bg-slate-50 p-4 rounded-lg text-sm text-slate-700 whitespace-pre-wrap font-mono">
                        {interview.transcript}
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-12 px-4 border-2 border-dashed border-slate-100 rounded-lg bg-slate-50/50">
                    <FileText className="w-8 h-8 text-slate-300 mb-3" />
                    <h4 className="text-sm font-medium text-slate-700 mb-1">No Recording Yet</h4>
                    <p className="text-xs text-slate-500 max-w-sm text-center">
                      Once the candidate completes their browser interview, the recording and transcript will appear here.
                    </p>
                  </div>
                )}
              </div>

              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
                <h3 className="text-sm font-semibold text-slate-900 mb-4 flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-slate-400" /> Interview Evaluation
                </h3>
                {isDograhEvaluation ? (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-slate-500">Disposition:</span>
                      <Badge variant="primary">{(rawEvaluation as DograhEvaluationEnvelope).call_disposition || 'unknown'}</Badge>
                      <span className="text-xs text-slate-500 ml-3">Call duration:</span>
                      <span className="text-xs font-medium text-slate-700">{formatDuration(callDuration)}</span>
                    </div>
                    {gatheredContext && Object.keys(gatheredContext).length > 0 && (
                      <div className="bg-slate-50 rounded-lg p-4">
                        <p className="text-xs font-semibold text-slate-500 mb-2 uppercase tracking-wide">Gathered Context</p>
                        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2">
                          {Object.entries(gatheredContext).map(([key, value]) => (
                            <div key={key}>
                              <dt className="text-xs text-slate-400">{key}</dt>
                              <dd className="text-sm text-slate-700 break-words">{String(value)}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    )}
                  </div>
                ) : interview?.evaluation ? (
                  <div className="bg-slate-50 p-4 rounded-lg text-sm text-slate-700">
                    <pre className="whitespace-pre-wrap font-mono text-xs">
                      {JSON.stringify(interview.evaluation, null, 2)}
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

              {interview?.link_expires_at && interview.status !== 'COMPLETED' && (
                <p className="text-xs text-slate-400 text-right">
                  Link expires {format(new Date(interview.link_expires_at), 'PPp')}
                </p>
              )}

            </div>

          </div>
        </div>
      </div>
    </div>
  );
};
