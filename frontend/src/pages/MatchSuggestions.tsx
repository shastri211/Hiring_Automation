import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, Users2, GitMerge, X, Undo2, Mail, Phone, Briefcase } from 'lucide-react';
import {
  useMatchSuggestions,
  useMergeMatchSuggestion,
  useRejectMatchSuggestion,
  useUnmergeCandidate,
} from '../hooks/useCandidateIdentity';
import { useConfirm } from '../hooks/useConfirm';
import { Badge, Button, EmptyState, ErrorState, PageHeader, Skeleton, StatusDot, Tabs } from '../components/ui';
import type { BadgeVariant } from '../utils/decision';
import type { CandidateMatchSuggestion, CandidateSummary, MatchSuggestionStatus } from '../types';

const STATUS_TABS: { value: MatchSuggestionStatus; label: string }[] = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'MERGED', label: 'Merged' },
  { value: 'REJECTED', label: 'Rejected' },
];

const STATUS_VARIANT: Record<MatchSuggestionStatus, BadgeVariant> = {
  PENDING: 'warning',
  MERGED: 'success',
  REJECTED: 'neutral',
};

const CandidateColumn = ({ candidate, label }: { candidate: CandidateSummary; label: string }) => (
  <div className="min-w-0 flex-1">
    <p className="text-eyebrow mb-1.5">{label}</p>
    <p className="truncate text-sm font-medium text-[var(--text-primary)]">
      {candidate.canonical_name || `Candidate #${candidate.id}`}
    </p>
    <dl className="mt-2 space-y-1 text-sm text-[var(--text-secondary)]">
      <div className="flex items-center gap-2 truncate">
        <dt className="sr-only">Email</dt>
        <Mail size={13} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
        <dd className="truncate">{candidate.primary_email || '—'}</dd>
      </div>
      <div className="flex items-center gap-2">
        <dt className="sr-only">Phone</dt>
        <Phone size={13} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
        <dd>{candidate.primary_phone || '—'}</dd>
      </div>
      <div className="flex items-center gap-2">
        <dt className="sr-only">Applications</dt>
        <Briefcase size={13} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
        <dd>{candidate.applications_count} application{candidate.applications_count === 1 ? '' : 's'}</dd>
      </div>
    </dl>
  </div>
);

const SuggestionRow = ({ suggestion }: { suggestion: CandidateMatchSuggestion }) => {
  const confirm = useConfirm();
  const mergeMutation = useMergeMatchSuggestion();
  const rejectMutation = useRejectMatchSuggestion();
  const unmergeMutation = useUnmergeCandidate();

  const aName = suggestion.candidate_a.canonical_name || `Candidate #${suggestion.candidate_a.id}`;
  const bName = suggestion.candidate_b.canonical_name || `Candidate #${suggestion.candidate_b.id}`;

  const handleMerge = async () => {
    const ok = await confirm({
      title: 'Merge these candidates?',
      description: `"${bName}" will be merged into "${aName}" - every resume and application "${bName}" has stays intact and now resolves to "${aName}" everywhere. This can be undone from either candidate's profile.`,
      confirmLabel: 'Merge',
    });
    if (ok) mergeMutation.mutate(suggestion.id);
  };

  const handleReject = async () => {
    const ok = await confirm({
      title: 'Dismiss this suggestion?',
      description: `Marks these two as distinct people. You can still merge them manually later if you change your mind.`,
      confirmLabel: 'Dismiss',
    });
    if (ok) rejectMutation.mutate(suggestion.id);
  };

  const handleUndoMerge = async () => {
    const ok = await confirm({
      title: 'Undo this merge?',
      description: `Restores "${bName}" as its own separate candidate, distinct from "${aName}" again.`,
      confirmLabel: 'Undo Merge',
    });
    if (ok) unmergeMutation.mutate(suggestion.candidate_b_id);
  };

  const isBusy = mergeMutation.isPending || rejectMutation.isPending || unmergeMutation.isPending;

  return (
    <article aria-label={`${aName} and ${bName}`} className="p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <StatusDot variant={STATUS_VARIANT[suggestion.status]}>
            {suggestion.status.charAt(0) + suggestion.status.slice(1).toLowerCase()}
          </StatusDot>
          <Badge>{Math.round(suggestion.confidence * 100)}% confidence</Badge>
          {suggestion.signals && Object.keys(suggestion.signals).length > 0 && (
            <span className="text-caption">
              Matched on: {Object.keys(suggestion.signals).map((k) => k.replace(/_/g, ' ')).join(', ')}
            </span>
          )}
        </div>
        <span className="text-caption">
          {suggestion.created_at ? formatDistanceToNow(new Date(suggestion.created_at), { addSuffix: true }) : ''}
        </span>
      </div>

      <div className="flex flex-col gap-6 sm:flex-row sm:gap-4">
        <CandidateColumn candidate={suggestion.candidate_a} label="Existing candidate" />
        <div aria-hidden="true" className="hidden items-center text-[var(--text-tertiary)] sm:flex">
          <GitMerge size={18} />
        </div>
        <CandidateColumn candidate={suggestion.candidate_b} label="New candidate" />
      </div>

      {(suggestion.resume_filename || suggestion.job_title) && (
        <p className="text-caption mt-4 border-t border-[var(--border-light)] pt-4">
          Flagged from {suggestion.resume_filename || 'a resume'}
          {suggestion.job_title ? ` for ${suggestion.job_title}` : ''}.
        </p>
      )}

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        {suggestion.status === 'PENDING' && (
          <>
            <Button variant="secondary" onClick={handleReject} disabled={isBusy}>
              {rejectMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <X size={14} aria-hidden="true" />}
              Not the same person
            </Button>
            <Button onClick={handleMerge} disabled={isBusy}>
              {mergeMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <GitMerge size={14} aria-hidden="true" />}
              Merge
            </Button>
          </>
        )}
        {suggestion.status === 'MERGED' && (
          <Button variant="secondary" onClick={handleUndoMerge} disabled={isBusy}>
            {unmergeMutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Undo2 size={14} aria-hidden="true" />}
            Undo merge
          </Button>
        )}
      </div>
    </article>
  );
};

export const MatchSuggestions = () => {
  const [status, setStatus] = useState<MatchSuggestionStatus>('PENDING');
  const { data, isLoading, isError, error, refetch } = useMatchSuggestions(status);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        className="mb-6"
        title="Duplicate candidates"
        subtitle="Candidates auto-flagged as possible duplicates by matching phone number, awaiting your review."
      />

      <Tabs<MatchSuggestionStatus> aria-label="Suggestion status" tabs={STATUS_TABS} value={status} onChange={setStatus} className="mb-4" />

      {isLoading ? (
        <div className="space-y-3" aria-hidden="true">
          {[0, 1].map((i) => <Skeleton key={i} className="h-44 w-full" />)}
        </div>
      ) : isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState
            title="Failed to load suggestions"
            message={error instanceof Error ? error.message : undefined}
            onRetry={() => refetch()}
          />
        </div>
      ) : !data || data.length === 0 ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <EmptyState
            icon={<Users2 size={20} />}
            title={status === 'PENDING' ? 'No pending duplicates' : `No ${status.toLowerCase()} suggestions`}
            description={
              status === 'PENDING'
                ? "You're all caught up - new suggestions appear here automatically when a resume's phone number matches an existing candidate."
                : 'Suggestions you review will show up here.'
            }
          />
        </div>
      ) : (
        <div className="divide-y divide-[var(--border-light)] rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          {data.map((suggestion) => (
            <SuggestionRow key={suggestion.id} suggestion={suggestion} />
          ))}
        </div>
      )}
    </div>
  );
};
