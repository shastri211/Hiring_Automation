import { useState } from 'react';
import { CheckCircle2, Clock, Eraser, Loader2, RefreshCw, Save, ShieldOff, XCircle } from 'lucide-react';
import type { CandidateDecision, ScreeningResultResponse, CandidateProfileDetail } from '../../types';
import { useSaveNotes } from '../../hooks/useDecisionMutation';
import { cn } from '../../utils/cn';
import { variantButtonClasses } from '../../utils/decision';
import { Alert, Badge, Button, FitScore, Section, Textarea } from '../ui';

/**
 * Presentational building blocks shared by the Candidate Drawer (quick review)
 * and Candidate 360 (full profile). They own no data fetching beyond the
 * decision/notes mutation; both surfaces feed them the same API responses.
 */

// -----------------------------------------------------------------------------
// Fit score
// -----------------------------------------------------------------------------
export const ScoreVisualizer = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  const score = screening.score;
  if (score === null || score === undefined) return null;

  return (
    <div>
      <p className="text-eyebrow mb-3">AI fit score</p>
      <FitScore score={score} size="lg" />
    </div>
  );
};

// -----------------------------------------------------------------------------
// Decision controls
// -----------------------------------------------------------------------------
const DECISIONS: { value: Exclude<CandidateDecision, null | 'PRE_SCREENED_OUT'>; label: string; short: string; icon: typeof CheckCircle2; tone: 'success' | 'warning' | 'danger' }[] = [
  { value: 'SHORTLIST', label: 'Shortlist', short: 'Shortlist', icon: CheckCircle2, tone: 'success' },
  { value: 'REVIEW', label: 'Move to review', short: 'Review', icon: Clock, tone: 'warning' },
  { value: 'REJECT', label: 'Reject', short: 'Reject', icon: XCircle, tone: 'danger' },
];

/**
 * DecisionControlBar — Shortlist / Review / Reject (+ Clear). The pressed state
 * uses the same decision colors as everywhere else (variantButtonClasses).
 * `stacked` is the full-width vertical form used in the Candidate 360 sidebar;
 * the default is a compact inline group for the drawer.
 */
export const DecisionControlBar = ({
  decision,
  isPending,
  onDecision,
  stacked = false,
}: {
  decision?: CandidateDecision;
  isPending: boolean;
  onDecision: (d: CandidateDecision | null) => void;
  stacked?: boolean;
}) => (
  <div role="group" aria-label="Decision" className={cn(stacked ? 'flex flex-col gap-2' : 'flex flex-wrap items-center gap-2')}>
    {DECISIONS.map(({ value, label, short, icon: Icon, tone }) => {
      const active = decision === value;
      return (
        <button
          key={value}
          type="button"
          onClick={() => onDecision(value)}
          disabled={isPending}
          aria-pressed={active}
          className={cn(
            'transition-base focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md border px-3.5 text-sm font-medium disabled:opacity-50',
            stacked && 'w-full',
            active
              ? `${variantButtonClasses[tone]} border-current`
              : 'border-[var(--border-strong)] bg-[var(--bg-surface)] text-[var(--text-primary)] hover:bg-[var(--bg-hover)]'
          )}
        >
          <Icon size={15} aria-hidden="true" /> {stacked ? label : short}
        </button>
      );
    })}
    {decision && (
      <button
        type="button"
        onClick={() => onDecision(null)}
        disabled={isPending}
        className={cn(
          'transition-base focus-ring inline-flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50',
          !stacked && 'ml-auto'
        )}
      >
        <Eraser size={14} aria-hidden="true" /> {stacked ? 'Clear decision' : 'Clear'}
      </button>
    )}
  </div>
);

// -----------------------------------------------------------------------------
// Recruiter notes — saved on their own (useSaveNotes sends only the note), so
// saving never re-submits the decision or re-triggers its side-effects.
// -----------------------------------------------------------------------------
export const RecruiterNotes = ({
  jobId, resumeId, savedNotes,
}: {
  jobId: number;
  resumeId: number;
  savedNotes?: string | null;
}) => {
  const mutation = useSaveNotes(jobId);
  // null = untouched, so the field always reflects the saved value until edited.
  const [draft, setDraft] = useState<string | null>(null);
  const saved = savedNotes || '';
  const value = draft ?? saved;
  const dirty = draft !== null && draft !== saved;

  return (
    <div>
      <label htmlFor={`notes-${resumeId}`} className="text-eyebrow mb-2 block">Recruiter notes</label>
      <Textarea
        id={`notes-${resumeId}`}
        rows={3}
        placeholder="Add private notes about this candidate…"
        value={value}
        onChange={(e) => setDraft(e.target.value)}
      />
      <div className="mt-2 flex justify-end">
        <Button
          variant="secondary"
          size="sm"
          disabled={mutation.isPending || !dirty}
          onClick={() =>
            mutation.mutate({ resumeId, notes: value }, { onSuccess: () => setDraft(null) })
          }
        >
          {mutation.isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <Save size={14} aria-hidden="true" />}
          Save notes
        </Button>
      </div>
    </div>
  );
};

// -----------------------------------------------------------------------------
// Skills
// -----------------------------------------------------------------------------
export const ExtractedSkills = ({ profile, limit = 15 }: { profile?: CandidateProfileDetail | null; limit?: number }) => {
  const skills: string[] = Array.isArray(profile?.skills) ? profile.skills : [];
  return skills.length > 0 ? (
    <div className="flex flex-wrap gap-1.5">
      {skills.slice(0, limit).map((s, i) => <Badge key={i}>{s}</Badge>)}
      {skills.length > limit && <span className="py-0.5 text-xs text-[var(--text-secondary)]">+{skills.length - limit} more</span>}
    </div>
  ) : (
    <span className="text-sm italic text-[var(--text-tertiary)]">No skills identified</span>
  );
};

// -----------------------------------------------------------------------------
// Evaluation lists
// -----------------------------------------------------------------------------
const BulletList = ({ items, empty, marker }: { items?: string[] | null; empty: string; marker: 'strength' | 'gap' | 'neutral' }) =>
  items && items.length > 0 ? (
    <ul className="space-y-2 text-sm">
      {items.map((text, i) => (
        <li key={i} className="flex gap-2.5 leading-relaxed text-[var(--text-primary)]">
          <span
            aria-hidden="true"
            className={cn(
              'mt-[0.55rem] h-1.5 w-1.5 shrink-0 rounded-full',
              marker === 'strength' ? 'bg-[var(--color-success-500)]' : marker === 'gap' ? 'bg-[var(--color-danger-500)]' : 'bg-[var(--color-neutral-400)]'
            )}
          />
          <span>{text}</span>
        </li>
      ))}
    </ul>
  ) : (
    <p className="text-sm italic text-[var(--text-tertiary)]">{empty}</p>
  );

export const StrengthsList = ({ items }: { items?: string[] | null }) => (
  <BulletList items={items} marker="strength" empty="None identified" />
);
export const GapsList = ({ items }: { items?: string[] | null }) => (
  <BulletList items={items} marker="gap" empty="None identified" />
);
export const EvidenceList = ({ items }: { items?: string[] | null }) => (
  <BulletList items={items} marker="neutral" empty="No evidence provided" />
);

/** Strengths and gaps side by side (stacked on narrow containers). */
export const ScreeningAnalysis = ({ screening }: { screening?: ScreeningResultResponse | null }) => {
  if (!screening) return null;
  return (
    <div className="grid gap-x-10 gap-y-8 sm:grid-cols-2">
      <Section title="Key strengths"><StrengthsList items={screening.strengths} /></Section>
      <Section title="Potential gaps"><GapsList items={screening.gaps} /></Section>
    </div>
  );
};

// -----------------------------------------------------------------------------
// Banners
// -----------------------------------------------------------------------------

/**
 * EvaluationFailedBanner — shown when every configured LLM provider failed for
 * this one candidate (screener.py's per-candidate fallback path). Without it
 * the score is simply absent and the evaluation lists read "None identified",
 * indistinguishable from a genuine (if uninformative) outcome.
 */
export const EvaluationFailedBanner = ({ onRetry, isPending }: { onRetry: () => void; isPending: boolean }) => (
  <Alert
    variant="danger"
    title="AI evaluation failed"
    action={
      <Button variant="secondary" size="sm" onClick={onRetry} disabled={isPending}>
        {isPending ? <Loader2 size={14} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={14} aria-hidden="true" />}
        Retry
      </Button>
    }
  >
    Every configured LLM provider failed for this candidate — usually a transient outage, not a resume problem. Retry once it&apos;s cleared.
  </Alert>
);

/**
 * CandidateStatusBanner — shown when there is no usable screening result yet.
 * Covers PRE_SCREENED_OUT, FAILED processing, in-flight processing, and
 * processed-but-not-screened. Replaces blank space that otherwise confuses users.
 */
export const CandidateStatusBanner = ({
  resumeStatus, decision, errorMessage,
}: {
  resumeStatus?: string | null;
  decision?: string | null;
  errorMessage?: string | null;
}) => {
  // PRE_SCREENED_OUT is stored in decision, not resume status
  if (decision === 'PRE_SCREENED_OUT') {
    return (
      <Alert variant="warning" icon={<ShieldOff size={16} />} title="Pre-screened out">
        This candidate did not meet the semantic similarity threshold for this job and was filtered before LLM evaluation. The semantic score is preserved; no AI evaluation was consumed.
      </Alert>
    );
  }
  if (resumeStatus === 'FAILED') {
    return (
      <Alert variant="danger" title="Processing failed">
        {errorMessage || 'An error occurred while processing this resume. It may need to be re-uploaded.'}
      </Alert>
    );
  }
  if (resumeStatus === 'PROCESSING' || resumeStatus === 'UPLOADED') {
    return (
      <Alert variant="info" icon={<Clock size={16} className="animate-pulse" />} title="Processing in progress">
        This resume is being processed. Screening results appear here once the pipeline completes — refresh to check for updates.
      </Alert>
    );
  }
  if (resumeStatus === 'READY') {
    return (
      <Alert variant="info" icon={<Clock size={16} />} title="Awaiting screening">
        This resume has been processed and is waiting for a screening run. Results appear once screening runs.
      </Alert>
    );
  }
  return null;
};
