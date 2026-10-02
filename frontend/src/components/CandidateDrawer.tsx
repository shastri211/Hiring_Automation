import { useRef } from 'react';
import { ChevronRight, ExternalLink, Mail, Phone } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { resumesApi } from '../api/resumes';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation, useRetryEvaluation } from '../hooks/useDecisionMutation';
import {
  Button, Drawer, DrawerBody, DrawerContent, DrawerFooter, DrawerHeader, ErrorState, FitScore, Section, Skeleton,
} from './ui';
import {
  CandidateStatusBanner,
  DecisionControlBar,
  EvaluationFailedBanner,
  EvidenceList,
  GapsList,
  RecruiterNotes,
  StrengthsList,
} from './candidate/CandidateComponents';
import { DecisionStatus } from './candidate/ScreeningCells';
import { formatSemantic } from '../utils/format';
import { getInitials } from '../utils/initials';

interface CandidateDrawerProps {
  jobId: number;
  resumeId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onView360?: () => void;
}

/**
 * CandidateDrawer — the QUICK REVIEW surface: who they are, how well they fit,
 * why, and the decision. Deliberately not a compressed Candidate 360 - work
 * history, education, skills, outreach and identity tools live on the full
 * profile, one click away.
 */
export const CandidateDrawer = ({ jobId, resumeId, isOpen, onClose, onView360 }: CandidateDrawerProps) => {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId!),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId!),
    enabled: isOpen && resumeId !== null,
  });

  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: isOpen,
  });

  // The drawer is opened from a table row (not a Radix trigger), so Radix has no
  // element to hand focus back to on close. Remember whatever had focus when it
  // opened and return there, so keyboard users land back on their row.
  const returnFocusTo = useRef<HTMLElement | null>(null);

  const decisionMutation = useDecisionMutation(jobId);
  const retryEvaluation = useRetryEvaluation(jobId);

  const screening = data?.screening;
  const name = data?.profile?.name || (resumeId !== null ? `Candidate #${resumeId}` : 'Candidate');
  const summary = data?.profile?.summary;
  const hasScoredEvaluation = !!screening && screening.decision !== 'PRE_SCREENED_OUT';
  const leadEvidence = screening?.evidence?.[0];
  const moreEvidence = screening?.evidence?.slice(1) ?? [];
  const showStatusBanner = !screening || screening.decision === 'PRE_SCREENED_OUT';

  return (
    <Drawer open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DrawerContent
        onOpenAutoFocus={() => {
          returnFocusTo.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
        }}
        onCloseAutoFocus={(e) => {
          e.preventDefault();
          returnFocusTo.current?.focus();
        }}
      >
        <DrawerHeader
          title={isLoading ? 'Loading…' : name}
          description={job?.title ? `Applying for ${job.title}` : 'Candidate application'}
          leading={
            <span
              aria-hidden="true"
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary-subtle-bg)] text-sm font-semibold text-[var(--color-primary-subtle-text)]"
            >
              {isLoading ? '' : getInitials(data?.profile?.name)}
            </span>
          }
        />

        <DrawerBody className="space-y-7">
          {isLoading && (
            <div className="space-y-6" aria-hidden="true">
              <Skeleton className="h-4 w-48" />
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}

          {isError && <ErrorState className="py-10" title="Failed to load candidate details" onRetry={() => refetch()} />}

          {data && (
            <>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-[var(--text-secondary)]">
                <DecisionStatus candidate={{ status: screening?.status ?? data.status, decision: screening?.decision, evaluation_failed: screening?.evaluation_failed }} />
                {data.profile?.email && (
                  <a href={`mailto:${data.profile.email}`} className="focus-ring inline-flex min-w-0 items-center gap-1.5 rounded hover:text-[var(--text-primary)]">
                    <Mail size={14} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
                    <span className="truncate">{data.profile.email}</span>
                  </a>
                )}
                {data.profile?.phone && (
                  <span className="inline-flex items-center gap-1.5">
                    <Phone size={14} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" /> {data.profile.phone}
                  </span>
                )}
              </div>

              {screening?.evaluation_failed && (
                <EvaluationFailedBanner onRetry={() => retryEvaluation.mutate(resumeId!)} isPending={retryEvaluation.isPending} />
              )}
              {showStatusBanner && (
                <CandidateStatusBanner
                  resumeStatus={screening?.status ?? data.status}
                  decision={screening?.decision ?? null}
                  errorMessage={screening?.error_message ?? data.error_message ?? null}
                />
              )}

              {hasScoredEvaluation && screening.score != null && (
                <section aria-label="Fit score">
                  <p className="text-eyebrow mb-3">AI fit score</p>
                  <FitScore score={screening.score} size="lg" />
                  <p className="text-caption tabular mt-3">Semantic match {formatSemantic(screening.semantic_score)}</p>
                </section>
              )}

              {hasScoredEvaluation && (leadEvidence || summary) && (
                <Section title="AI summary">
                  {leadEvidence && <p className="text-sm leading-relaxed text-[var(--text-primary)]">{leadEvidence}</p>}
                  {summary && (
                    <p className="mt-2 line-clamp-4 text-sm leading-relaxed text-[var(--text-secondary)]">{summary}</p>
                  )}
                </Section>
              )}

              {hasScoredEvaluation && (
                <>
                  <Section title="Key strengths"><StrengthsList items={screening.strengths} /></Section>
                  <Section title="Potential gaps"><GapsList items={screening.gaps} /></Section>
                  {moreEvidence.length > 0 && (
                    <details className="text-sm">
                      <summary className="transition-base focus-ring cursor-pointer select-none rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                        More evidence ({moreEvidence.length})
                      </summary>
                      <div className="mt-3"><EvidenceList items={moreEvidence} /></div>
                    </details>
                  )}
                </>
              )}

              {resumeId !== null && (
                <RecruiterNotes
                  key={resumeId}
                  jobId={jobId}
                  resumeId={resumeId}
                  savedNotes={screening?.notes}
                  decision={screening?.decision}
                />
              )}
            </>
          )}
        </DrawerBody>

        <DrawerFooter className="flex-col items-stretch gap-3">
          {data && (
            <DecisionControlBar
              decision={screening?.decision}
              isPending={decisionMutation.isPending}
              onDecision={(d) => {
                if (resumeId !== null) decisionMutation.mutate({ resumeId, decision: d });
              }}
            />
          )}
          <div className="flex items-center justify-between gap-3 border-t border-[var(--border-light)] pt-3">
          {data?.filename ? (
            <a
              href={resumesApi.getResumeFileUrl(resumeId ?? 0)}
              target="_blank"
              rel="noopener noreferrer"
              className="focus-ring inline-flex items-center gap-1.5 rounded px-1 text-sm font-medium text-[var(--color-primary-600)] hover:text-[var(--color-primary-700)]"
            >
              <ExternalLink size={15} aria-hidden="true" /> Original resume
            </a>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-1 text-sm text-[var(--text-tertiary)]" title="Original resume unavailable">
              <ExternalLink size={15} aria-hidden="true" className="opacity-50" /> Resume unavailable
            </span>
          )}
          <Button onClick={() => onView360?.()} disabled={!data}>
            View full profile <ChevronRight size={15} aria-hidden="true" />
          </Button>
          </div>
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
};
