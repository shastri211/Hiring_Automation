import { useEffect, useState } from 'react';
import { GitMerge, Loader2, Search } from 'lucide-react';
import { useCandidateSearch, useMergeCandidates } from '../../hooks/useCandidateIdentity';
import { Button } from '../ui/Button';
import { Dialog, DialogContent, DialogDescription, DialogTitle, Input } from '../ui';
import type { CandidateResponse } from '../../types';

const candidateLabel = (c: Pick<CandidateResponse, 'id' | 'canonical_name' | 'primary_email'>) =>
  c.canonical_name || c.primary_email || `Candidate #${c.id}`;

// Manual counterpart to the automatic duplicate suggestions: folds this
// candidate record into another one the recruiter knows is the same person.
// Reversible from the Candidate Identity card ("Undo Merge").
export const MergeCandidateDialog = ({
  candidate,
  onClose,
}: {
  candidate: CandidateResponse;
  onClose: () => void;
}) => {
  const [term, setTerm] = useState('');
  const [debouncedTerm, setDebouncedTerm] = useState('');
  const [target, setTarget] = useState<CandidateResponse | null>(null);
  const merge = useMergeCandidates();

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedTerm(term), 300);
    return () => clearTimeout(timer);
  }, [term]);

  const search = useCandidateSearch(debouncedTerm, candidate.id);
  const searching = debouncedTerm.trim().length >= 2;

  const handleMerge = () => {
    if (!target) return;
    merge.mutate(
      { absorbed_candidate_id: candidate.id, into_candidate_id: target.id },
      { onSuccess: onClose }
    );
  };

  return (
    <Dialog open onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="flex items-center gap-2">
          <GitMerge className="w-5 h-5 text-[var(--color-primary-600)]" />
          Merge into another candidate
        </DialogTitle>
        <DialogDescription>
          Use this when <span className="font-medium">{candidateLabel(candidate)}</span> is the same person as an
          existing candidate. Their applications will be shown under the candidate you pick. You can undo this later.
        </DialogDescription>

        <div>
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <Input
              autoFocus
              value={term}
              onChange={(e) => { setTerm(e.target.value); setTarget(null); }}
              placeholder="Search by name, email or phone"
              className="pl-9"
              disabled={merge.isPending}
            />
          </div>

          <div className="mt-3 max-h-64 overflow-y-auto">
            {!searching ? (
              <p className="text-xs text-[var(--text-tertiary)] px-1">Type at least 2 characters.</p>
            ) : search.isLoading ? (
              <div className="flex justify-center p-4"><Loader2 className="w-5 h-5 animate-spin text-[var(--color-primary-500)]" /></div>
            ) : search.isError ? (
              <div className="flex items-center justify-between gap-3 p-3 rounded-md text-sm bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)]">
                <span>Could not search candidates.</span>
                <Button variant="secondary" size="sm" onClick={() => search.refetch()}>Retry</Button>
              </div>
            ) : !search.data?.length ? (
              <p className="text-sm text-[var(--text-secondary)] px-1">No matching candidates.</p>
            ) : (
              <ul className="space-y-1" role="listbox" aria-label="Matching candidates">
                {search.data.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={target?.id === c.id}
                      onClick={() => setTarget(c)}
                      disabled={merge.isPending}
                      className={`w-full text-left px-3 py-2 rounded-md border text-sm transition-base ${
                        target?.id === c.id
                          ? 'border-[var(--color-primary-500)] bg-[var(--color-primary-50)]'
                          : 'border-[var(--border-light)] hover:bg-[var(--bg-hover)]'
                      }`}
                    >
                      <div className="font-medium text-[var(--text-primary)]">{candidateLabel(c)}</div>
                      <div className="text-xs text-[var(--text-secondary)]">
                        {[c.primary_email, c.primary_phone].filter(Boolean).join(' · ') || `Candidate #${c.id}`}
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {target && (
            <p className="mt-3 text-sm text-[var(--text-secondary)]">
              <span className="font-medium text-[var(--text-primary)]">{candidateLabel(candidate)}</span> will be merged into{' '}
              <span className="font-medium text-[var(--text-primary)]">{candidateLabel(target)}</span>.
            </p>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border-light)] mt-2">
          <Button variant="secondary" onClick={onClose} disabled={merge.isPending}>Cancel</Button>
          <Button onClick={handleMerge} disabled={!target || merge.isPending} className="flex items-center gap-2">
            {merge.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <GitMerge className="w-4 h-4" />}
            Merge
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
