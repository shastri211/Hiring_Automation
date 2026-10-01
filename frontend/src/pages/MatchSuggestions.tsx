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
import { Badge, Button, PageHeader } from '../components/ui';
import type { CandidateMatchSuggestion, CandidateSummary, MatchSuggestionStatus } from '../types';

const STATUS_TABS: { value: MatchSuggestionStatus; label: string }[] = [
  { value: 'PENDING', label: 'Pending' },
  { value: 'MERGED', label: 'Merged' },
  { value: 'REJECTED', label: 'Rejected' },
];

const FilterChip = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => (
  <button
    onClick={onClick}
    className={`transition-base px-4 py-1.5 rounded-full text-sm font-medium ${
      active
        ? 'bg-[var(--text-primary)] text-[var(--bg-surface)]'
        : 'bg-[var(--bg-hover)] text-[var(--text-secondary)] hover:bg-[var(--border-light)]'
    }`}
  >
    {label}
  </button>
);

const CandidateColumn = ({ candidate, label }: { candidate: CandidateSummary; label: string }) => (
  <div className="flex-1 min-w-0">
    <div className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide mb-1.5">{label}</div>
    <div className="font-medium text-[var(--text-primary)] truncate">
      {candidate.canonical_name || `Candidate #${candidate.id}`}
    </div>
    <div className="mt-1.5 space-y-1 text-sm text-[var(--text-secondary)]">
      <div className="flex items-center gap-1.5 truncate">
        <Mail className="w-3.5 h-3.5 shrink-0 text-[var(--text-tertiary)]" />
        <span className="truncate">{candidate.primary_email || '—'}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Phone className="w-3.5 h-3.5 shrink-0 text-[var(--text-tertiary)]" />
        <span>{candidate.primary_phone || '—'}</span>
      </div>
      <div className="flex items-center gap-1.5">
        <Briefcase className="w-3.5 h-3.5 shrink-0 text-[var(--text-tertiary)]" />
        <span>{candidate.applications_count} application{candidate.applications_count === 1 ? '' : 's'}</span>
      </div>
    </div>
  </div>
);

const statusBadgeVariant = (status: MatchSuggestionStatus) =>
  status === 'MERGED' ? 'success' : status === 'REJECTED' ? 'danger' : 'warning';

const SuggestionCard = ({ suggestion }: { suggestion: CandidateMatchSuggestion }) => {
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
    <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-[var(--shadow-sm)] p-6">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={statusBadgeVariant(suggestion.status)}>{suggestion.status}</Badge>
          <Badge variant="neutral">{Math.round(suggestion.confidence * 100)}% confidence</Badge>
          {suggestion.signals && Object.keys(suggestion.signals).length > 0 && (
            <span className="text-xs text-[var(--text-tertiary)]">
              Matched on: {Object.keys(suggestion.signals).map((k) => k.replace(/_/g, ' ')).join(', ')}
            </span>
          )}
        </div>
        <span className="text-xs text-[var(--text-tertiary)]">
          {suggestion.created_at ? formatDistanceToNow(new Date(suggestion.created_at), { addSuffix: true }) : ''}
        </span>
      </div>

      <div className="flex flex-col sm:flex-row gap-6 sm:gap-4">
        <CandidateColumn candidate={suggestion.candidate_a} label="Existing candidate" />
        <div className="hidden sm:flex items-center text-[var(--text-tertiary)]">
          <GitMerge className="w-5 h-5" />
        </div>
        <CandidateColumn candidate={suggestion.candidate_b} label="New candidate" />
      </div>

      {(suggestion.resume_filename || suggestion.job_title) && (
        <p className="mt-4 pt-4 border-t border-[var(--border-light)] text-xs text-[var(--text-tertiary)]">
          Flagged from {suggestion.resume_filename || 'a resume'}
          {suggestion.job_title ? ` for ${suggestion.job_title}` : ''}.
        </p>
      )}

      <div className="mt-4 flex justify-end gap-3">
        {suggestion.status === 'PENDING' && (
          <>
            <Button variant="secondary" onClick={handleReject} disabled={isBusy} className="flex items-center gap-2">
              {rejectMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <X className="w-4 h-4" />}
              Not the same person
            </Button>
            <Button onClick={handleMerge} disabled={isBusy} className="flex items-center gap-2">
              {mergeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitMerge className="w-4 h-4" />}
              Merge
            </Button>
          </>
        )}
        {suggestion.status === 'MERGED' && (
          <Button variant="secondary" onClick={handleUndoMerge} disabled={isBusy} className="flex items-center gap-2">
            {unmergeMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Undo2 className="w-4 h-4" />}
            Undo Merge
          </Button>
        )}
      </div>
    </div>
  );
};

export const MatchSuggestions = () => {
  const [status, setStatus] = useState<MatchSuggestionStatus>('PENDING');
  const { data, isLoading, isError, error, refetch } = useMatchSuggestions(status);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <PageHeader
        className="mb-8"
        eyebrow={
          <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center mb-2">
            <Users2 className="w-6 h-6" />
          </div>
        }
        title="Duplicate Candidates"
        subtitle="Candidates auto-flagged as possible duplicates by matching phone number, awaiting your review."
      />

      <div className="flex gap-2 mb-6">
        {STATUS_TABS.map((tab) => (
          <FilterChip key={tab.value} active={status === tab.value} label={tab.label} onClick={() => setStatus(tab.value)} />
        ))}
      </div>

      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
        </div>
      ) : isError ? (
        <div className="p-8 text-center bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl">
          <p className="text-[var(--color-danger-600)] mb-4">
            Failed to load suggestions{error instanceof Error ? `: ${error.message}` : '.'}
          </p>
          <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
        </div>
      ) : !data || data.length === 0 ? (
        <div className="text-center py-20 bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl">
          <Users2 className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
          <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">
            {status === 'PENDING' ? 'No pending duplicates' : `No ${status.toLowerCase()} suggestions`}
          </h3>
          <p className="text-[var(--text-secondary)]">
            {status === 'PENDING'
              ? "You're all caught up - new suggestions appear here automatically when a resume's phone number matches an existing candidate."
              : 'Suggestions you review will show up here.'}
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.map((suggestion) => (
            <SuggestionCard key={suggestion.id} suggestion={suggestion} />
          ))}
        </div>
      )}
    </div>
  );
};
