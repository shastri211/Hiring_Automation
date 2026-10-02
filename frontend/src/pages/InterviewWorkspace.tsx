import { useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import {
  ArrowLeft, Mic, Clock, FileText, PlayCircle, BarChart3, AlertCircle, CheckCircle2,
  Link as LinkIcon, Copy, RefreshCw, ExternalLink, UserX, XCircle,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { format, formatDistanceToNow } from 'date-fns';
import { toast } from 'sonner';
import { jobsApi } from '../api/jobs';
import { api } from '../api';
import { queryKeys } from '../api/queryKeys';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import { Alert, Badge, Button, EmptyState, PageHeader, Section, Skeleton, StatusDot } from '../components/ui';
import { getInterviewStatusBadgeVariant, interviewStatusLabel } from '../utils/status';
import { ratingVariant, parseRecommendation } from '../utils/interviewEvaluation';
import { getErrorMessage } from '../utils/errors';
import type { InterviewEvaluationData, IntegrationResponse } from '../types';

// A structured Q&A field is worth a row in the grid only once the interview
// has actually said something about it.
const QA_FIELDS: { key: keyof InterviewEvaluationData; label: string }[] = [
  { key: 'years_relevant_experience', label: 'Relevant experience' },
  { key: 'key_skills_mentioned', label: 'Key skills mentioned' },
  { key: 'notice_period', label: 'Notice period' },
  { key: 'salary_expectation', label: 'Salary expectation' },
  { key: 'motivation_summary', label: 'Motivation' },
  { key: 'concerns_or_gaps', label: 'Concerns / gaps' },
];

const STEPS: { key: string; label: string }[] = [
  { key: 'PENDING', label: 'Requested' },
  { key: 'SCHEDULED', label: 'Link sent' },
  { key: 'IN_PROGRESS', label: 'In progress' },
  { key: 'COMPLETED', label: 'Completed' },
];

function formatDuration(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

const LifecycleStepper = ({
  status, scheduledAt, completedAt, outcome, retryCount,
}: {
  status: string;
  scheduledAt?: string | null;
  completedAt?: string | null;
  outcome?: string | null;
  retryCount?: number;
}) => {
  if (status === 'FAILED') {
    return (
      <Alert variant="danger" icon={<AlertCircle size={16} />} title="Interview inconclusive">
        The interview did not reach a completed state{outcome ? ` (${outcome})` : ''}. You can resend the link or mark the candidate as declined if that&apos;s confirmed.
      </Alert>
    );
  }
  if (status === 'RESCHEDULE_PENDING') {
    return (
      <Alert variant="warning" icon={<AlertCircle size={16} />} title="System issue interrupted the interview">
        A provider/system issue ({outcome || 'unknown'}) cut the interview short - not the candidate&apos;s fault.
        {retryCount != null && <> Retry attempt {retryCount} used so far.</>} You can retry, subject to the retry limit.
      </Alert>
    );
  }
  if (status === 'NO_SHOW') {
    return (
      <Alert variant="danger" icon={<UserX size={16} />} title="No show">
        The candidate did not open the interview link before it expired. This is terminal - no automatic resend.
      </Alert>
    );
  }
  if (status === 'DECLINED') {
    return (
      <Alert variant="info" icon={<XCircle size={16} />} title="Candidate declined">
        The candidate declined to continue with the interview process.
      </Alert>
    );
  }

  const currentIndex = Math.max(0, STEPS.findIndex((s) => s.key === status));

  return (
    <ol className="relative space-y-5">
      {STEPS.map((step, i) => {
        const done = i <= currentIndex;
        const isCurrent = i === currentIndex;
        return (
          <li key={step.key} className="relative flex items-start gap-3" aria-current={isCurrent ? 'step' : undefined}>
            {i < STEPS.length - 1 && (
              <span aria-hidden="true" className={`absolute left-[0.5625rem] top-6 h-[calc(100%-0.25rem)] w-px ${i < currentIndex ? 'bg-[var(--accent)]' : 'bg-[var(--border-strong)]'}`} />
            )}
            <span
              aria-hidden="true"
              className={`relative mt-0.5 flex h-[1.125rem] w-[1.125rem] shrink-0 items-center justify-center rounded-full text-[10px] font-semibold ${
                done
                  ? 'bg-[var(--accent)] text-[var(--accent-fg)]'
                  : 'border border-[var(--border-input)] bg-[var(--bg-surface)] text-[var(--text-tertiary)]'
              }`}
            >
              {done ? '✓' : i + 1}
            </span>
            <div>
              <p className={`text-sm font-medium ${isCurrent ? 'text-[var(--text-primary)]' : done ? 'text-[var(--text-secondary)]' : 'text-[var(--text-tertiary)]'}`}>
                {step.label}
                <span className="sr-only">{done ? (isCurrent ? ' (current)' : ' (done)') : ' (upcoming)'}</span>
              </p>
              {step.key === 'SCHEDULED' && scheduledAt && (
                <p className="text-caption">{formatDistanceToNow(new Date(scheduledAt), { addSuffix: true })}</p>
              )}
              {step.key === 'COMPLETED' && completedAt && (
                <p className="text-caption">{formatDistanceToNow(new Date(completedAt), { addSuffix: true })}</p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
};

const InterviewWorkspaceView = () => {
  const { jobId: jobIdStr, resumeId: resumeIdStr } = useParams();
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
  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });

  const interview = candidate?.interview;
  const candidateName = candidate?.profile?.name || `Candidate #${resumeId}`;

  useBreadcrumbs([
    { label: 'Jobs', to: '/jobs' },
    { label: job?.title || 'Job', to: `/jobs/${jobId}` },
    { label: candidateName, to: `/jobs/${jobId}/candidates/${resumeId}` },
    { label: 'Interview' },
  ]);

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
    },
  });

  const resyncMutation = useMutation({
    mutationFn: () => jobsApi.resyncInterview(jobId, resumeId),
    onSuccess: (data) => {
      toast.success(data.message || 'Interview resynced.');
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, resumeId) });
    },
    onError: (err: { message?: string }) => toast.error(err.message || 'Failed to resync interview from Dograh.'),
  });

  const declineMutation = useMutation({
    mutationFn: () => jobsApi.declineInterview(jobId, resumeId),
    onSuccess: (data) => {
      toast.success(data.message || 'Interview marked as declined.');
      queryClient.invalidateQueries({ queryKey: queryKeys.candidateDetail(jobId, resumeId) });
    },
    onError: (err: { message?: string }) => toast.error(err.message || 'Failed to mark interview as declined.'),
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

  const evaluation = interview?.evaluation ?? null;
  const hasEvaluation = !!evaluation && Object.keys(evaluation).length > 0;
  const recommendation = parseRecommendation(evaluation?.interview_recommendation);
  const qaFieldsPresent = QA_FIELDS.filter((f) => evaluation?.[f.key]);
  const canTrigger = !interview || !['NO_SHOW', 'DECLINED', 'COMPLETED', 'SCHEDULED', 'IN_PROGRESS'].includes(interview.status);
  const canDecline = !!interview && !['COMPLETED', 'DECLINED', 'NO_SHOW'].includes(interview.status);

  return (
    <div className="mx-auto max-w-6xl">
      <Button variant="ghost" size="sm" onClick={handleBack} className="-ml-2.5 mb-3">
        <ArrowLeft size={14} aria-hidden="true" /> Back to candidate
      </Button>

      <PageHeader
        className="mb-6"
        title="Interview workspace"
        subtitle={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            {interview ? (
              <StatusDot variant={getInterviewStatusBadgeVariant(interview.status)} live={interview.status === 'IN_PROGRESS'}>
                {interviewStatusLabel(interview.status)}
              </StatusDot>
            ) : (
              <StatusDot variant="neutral">Not scheduled</StatusDot>
            )}
            <span>
              {isLoadingCandidate ? 'Loading candidate…' : (
                <Link to={`/jobs/${jobId}/candidates/${resumeId}`} className="focus-ring rounded font-medium text-[var(--text-primary)] hover:underline">{candidateName}</Link>
              )}
              {job?.title ? <> · {job.title.trim()}</> : <> · Job #{jobId}</>}
            </span>
            {interview?.provider === 'dograh' && <span className="text-caption">via Dograh</span>}
          </span>
        }
        actions={
          <>
            {interview?.interview_link && (
              <Button variant="secondary" onClick={handleCopyLink}>
                <Copy size={14} aria-hidden="true" /> Copy interview link
              </Button>
            )}
            {interview?.provider_run_id && interview.status !== 'COMPLETED' && (
              <Button variant="secondary" onClick={() => resyncMutation.mutate()} disabled={resyncMutation.isPending}>
                <RefreshCw size={14} aria-hidden="true" className={resyncMutation.isPending ? 'animate-spin' : ''} /> Resync
              </Button>
            )}
            {canDecline && (
              <Button variant="secondary" onClick={() => declineMutation.mutate()} disabled={declineMutation.isPending}>
                <UserX size={14} aria-hidden="true" /> Mark as declined
              </Button>
            )}
            {canTrigger && (
              <Button onClick={() => triggerMutation.mutate()} disabled={triggerMutation.isPending}>
                {triggerMutation.isPending ? 'Creating link…' : (
                  <><Mic size={14} aria-hidden="true" /> {interview ? 'Resend interview link' : 'Create interview link'}</>
                )}
              </Button>
            )}
          </>
        }
      />

      <div className="mb-6 space-y-3 empty:hidden">
        {!!candidateError && (
          <Alert variant="danger" title="Could not load candidate">{getErrorMessage(candidateError, 'Please try again.')}</Alert>
        )}
        {triggerResponse && (
          <Alert variant="success" icon={<CheckCircle2 size={16} />} title="Interview link ready">
            {triggerResponse.message}
            {interview?.interview_link && (
              <span className="mt-1.5 flex items-center gap-1 break-all text-xs">
                <LinkIcon size={12} aria-hidden="true" className="shrink-0" /> {interview.interview_link}
              </span>
            )}
          </Alert>
        )}
        {triggerError && <Alert variant="danger" title="Trigger failed">{triggerError}</Alert>}
      </div>

      <div className="grid grid-cols-1 gap-x-10 gap-y-9 lg:grid-cols-[17rem_minmax(0,1fr)]">
        <div className="lg:pr-2">
          <Section title="Lifecycle" icon={<Clock size={13} />}>
            {isLoadingCandidate ? (
              <div className="space-y-4" aria-hidden="true">
                {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-5 w-32" />)}
              </div>
            ) : interview ? (
              <LifecycleStepper
                status={interview.status}
                scheduledAt={interview.scheduled_at}
                completedAt={interview.completed_at}
                outcome={interview.outcome}
                retryCount={interview.retry_count}
              />
            ) : (
              <p className="text-body">
                <span className="font-medium text-[var(--text-primary)]">No interview scheduled.</span> Create an interview link to begin the process.
              </p>
            )}
            {interview?.link_expires_at && !['COMPLETED', 'NO_SHOW', 'DECLINED'].includes(interview.status) && (
              <p className="text-caption mt-5 border-t border-[var(--border-light)] pt-3">
                Link expires {format(new Date(interview.link_expires_at), 'PPp')}
              </p>
            )}
          </Section>
        </div>

        <div className="space-y-9 lg:border-l lg:border-[var(--border-light)] lg:pl-10">
          <Section title="Recording & transcript" icon={<PlayCircle size={13} />}>
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
                    className="focus-ring inline-flex items-center gap-1.5 rounded text-sm font-medium text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]"
                  >
                    <ExternalLink size={14} aria-hidden="true" /> View full transcript
                  </a>
                )}
                {!interview.transcript_url && interview.transcript && (
                  <div className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md border border-[var(--border-light)] bg-[var(--bg-app)] p-4 font-mono text-sm text-[var(--text-secondary)]">
                    {interview.transcript}
                  </div>
                )}
              </div>
            ) : (
              <EmptyState
                className="py-8"
                icon={<FileText size={20} />}
                title="No recording yet"
                description="Once the candidate completes their browser interview, the recording and transcript will appear here."
              />
            )}
          </Section>

          <Section title="Interview evaluation" icon={<BarChart3 size={13} />}>
            {hasEvaluation ? (
              <div className="space-y-5">
                {recommendation && (
                  <Alert
                    variant={recommendation.variant === 'success' ? 'success' : recommendation.variant === 'danger' ? 'danger' : 'warning'}
                    icon={recommendation.variant === 'success' ? <CheckCircle2 size={16} /> : recommendation.variant === 'danger' ? <AlertCircle size={16} /> : <Clock size={16} />}
                    title={recommendation.label}
                  >
                    {recommendation.reason || undefined}
                  </Alert>
                )}

                {(evaluation?.communication_clarity || evaluation?.demonstrated_skill_depth) && (
                  <div className="flex flex-wrap gap-x-8 gap-y-3">
                    {evaluation?.communication_clarity && (
                      <div>
                        <p className="text-eyebrow mb-1.5">Communication clarity</p>
                        <Badge variant={ratingVariant(evaluation.communication_clarity)}>{evaluation.communication_clarity}</Badge>
                      </div>
                    )}
                    {evaluation?.demonstrated_skill_depth && (
                      <div>
                        <p className="text-eyebrow mb-1.5">Demonstrated skill depth</p>
                        <Badge variant={ratingVariant(evaluation.demonstrated_skill_depth)}>{evaluation.demonstrated_skill_depth}</Badge>
                      </div>
                    )}
                  </div>
                )}

                {(evaluation?.call_disposition || evaluation?.call_duration_seconds != null) && (
                  <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-[var(--text-secondary)]">
                    {evaluation?.call_disposition && (
                      <span className="flex items-center gap-2">Call ended <Badge>{evaluation.call_disposition}</Badge></span>
                    )}
                    {evaluation?.call_duration_seconds != null && (
                      <span>Duration <span className="tabular font-medium text-[var(--text-primary)]">{formatDuration(evaluation.call_duration_seconds)}</span></span>
                    )}
                  </div>
                )}

                {qaFieldsPresent.length > 0 && (
                  <div className="border-t border-[var(--border-light)] pt-5">
                    <p className="text-eyebrow mb-3">From the conversation</p>
                    <dl className="grid grid-cols-1 gap-x-8 gap-y-4 sm:grid-cols-2">
                      {qaFieldsPresent.map(({ key, label }) => (
                        <div key={key}>
                          <dt className="text-caption">{label}</dt>
                          <dd className="mt-0.5 break-words text-sm text-[var(--text-primary)]">{String(evaluation?.[key])}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>
            ) : (
              <EmptyState
                className="py-8"
                icon={<BarChart3 size={20} />}
                title="No evaluation available"
                description="AI evaluation results and scoring will appear here once the interview completes."
              />
            )}
          </Section>
        </div>
      </div>
    </div>
  );
};

// Keyed by route params so the trigger success/error banners never carry over
// to a different candidate's workspace when only the URL changes.
export const InterviewWorkspace = () => {
  const { jobId, resumeId } = useParams();
  return <InterviewWorkspaceView key={`${jobId}-${resumeId}`} />;
};
