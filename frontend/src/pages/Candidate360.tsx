import { useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { ArrowLeft, Check, ExternalLink, GitMerge, Inbox, Mail, PackagePlus, Pencil, Phone, Undo2, Users2, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { resumesApi } from '../api/resumes';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation, useRetryEvaluation } from '../hooks/useDecisionMutation';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { useCandidate, useUpdateCandidateName, useUnmergeCandidate } from '../hooks/useCandidateIdentity';
import { useConfirm } from '../hooks/useConfirm';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import {
  Alert, Badge, Button, ErrorState, FitScore, IconButton, Input, LinkButton, Section, Skeleton,
} from '../components/ui';
import {
  CandidateStatusBanner,
  DecisionControlBar,
  EvaluationFailedBanner,
  EvidenceList,
  ExtractedSkills,
  RecruiterNotes,
  ScreeningAnalysis,
} from '../components/candidate/CandidateComponents';
import { DecisionStatus } from '../components/candidate/ScreeningCells';
import { formatSemantic } from '../utils/format';
import { CandidateTimeline } from '../components/candidate/CandidateTimeline';
import { InterviewSummary } from '../components/candidate/InterviewSummary';
import { OutreachHistory } from '../components/candidate/OutreachHistory';
import { MergeCandidateDialog } from '../components/candidate/MergeCandidateDialog';
import { getInitials } from '../utils/initials';

const CandidateIdentityPanel = ({ candidateId, applicationsCount }: { candidateId: number; applicationsCount?: number | null }) => {
  const { data: candidate, isLoading } = useCandidate(candidateId);
  const updateName = useUpdateCandidateName();
  const unmerge = useUnmergeCandidate();
  const confirm = useConfirm();
  const [isEditing, setIsEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');
  const [isMerging, setIsMerging] = useState(false);

  if (isLoading || !candidate) return null;

  const startEdit = () => {
    setNameInput(candidate.canonical_name || '');
    setIsEditing(true);
  };

  const saveName = () => {
    updateName.mutate(
      { candidateId, canonicalName: nameInput.trim() || null },
      { onSuccess: () => setIsEditing(false) }
    );
  };

  const handleUndoMerge = async () => {
    const ok = await confirm({
      title: 'Undo this merge?',
      description: `Restores this candidate as its own separate record, no longer merged into "${candidate.merged_into_name || `candidate #${candidate.merged_into_id}`}".`,
      confirmLabel: 'Undo Merge',
    });
    if (ok) unmerge.mutate(candidateId);
  };

  return (
    <Section title="Candidate identity" icon={<Users2 size={13} />}>
      {candidate.merged_into_id != null && (
        <Alert
          variant="warning"
          className="mb-3"
          action={
            <Button variant="secondary" size="sm" onClick={handleUndoMerge} disabled={unmerge.isPending}>
              <Undo2 size={13} aria-hidden="true" /> Undo merge
            </Button>
          }
        >
          This candidate record was merged into{' '}
          <span className="font-medium">{candidate.merged_into_name || `candidate #${candidate.merged_into_id}`}</span>.
        </Alert>
      )}

      <p className="text-eyebrow mb-1.5">Display name</p>
      {isEditing ? (
        <div className="flex items-center gap-1">
          <Input
            autoFocus
            aria-label="Display name"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') saveName(); if (e.key === 'Escape') setIsEditing(false); }}
            placeholder="Leave blank to use extracted name"
            className="h-8"
          />
          <IconButton label="Save name" tone="success" icon={<Check size={15} />} onClick={saveName} disabled={updateName.isPending} />
          <IconButton label="Cancel editing" icon={<X size={15} />} onClick={() => setIsEditing(false)} />
        </div>
      ) : (
        <div className="flex items-center justify-between gap-2">
          <span className="min-w-0 truncate text-sm text-[var(--text-primary)]">
            {candidate.canonical_name || <span className="text-[var(--text-tertiary)]">Using extracted name</span>}
          </span>
          <IconButton label="Edit display name" icon={<Pencil size={14} />} onClick={startEdit} />
        </div>
      )}

      {applicationsCount != null && (
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          Applied to {applicationsCount} job{applicationsCount === 1 ? '' : 's'} in total.
        </p>
      )}

      {candidate.merged_into_id == null && (
        <Button variant="secondary" size="sm" onClick={() => setIsMerging(true)} className="mt-3">
          <GitMerge size={13} aria-hidden="true" /> Merge into another candidate…
        </Button>
      )}
      {isMerging && <MergeCandidateDialog candidate={candidate} onClose={() => setIsMerging(false)} />}
    </Section>
  );
};

export const Candidate360 = () => {
  const { id: jobIdStr, resumeId: resumeIdStr } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  const jobId = parseInt(jobIdStr || '0', 10);
  const resumeId = parseInt(resumeIdStr || '0', 10);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.candidateDetail(jobId, resumeId),
    queryFn: () => jobsApi.getJobResultDetail(jobId, resumeId),
    enabled: !!jobId && !!resumeId,
  });
  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });

  const decisionMutation = useDecisionMutation(jobId);
  const retryEvaluation = useRetryEvaluation(jobId);
  const addToPool = useAddToTalentPool();

  const name = data?.profile?.name || `Candidate #${resumeId}`;
  useBreadcrumbs([
    { label: 'Jobs', to: '/jobs' },
    { label: job?.title || 'Job', to: `/jobs/${jobId}` },
    { label: 'Candidates', to: `/jobs/${jobId}/candidates` },
    { label: name },
  ]);

  const handleBack = () => {
    // Navigate back to the previous list with preserved state, or fallback to job detail
    if (location.state?.from) {
      navigate(-1);
    } else {
      navigate(`/jobs/${jobId}`);
    }
  };

  if (isLoading) {
    return (
      <div className="mx-auto grid max-w-6xl gap-10 lg:grid-cols-[19rem_minmax(0,1fr)]" aria-hidden="true">
        <div className="space-y-4">
          <Skeleton className="h-14 w-14 rounded-full" />
          <Skeleton className="h-7 w-48" />
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-32 w-full" />
        </div>
        <div className="space-y-4">
          <Skeleton className="h-6 w-56" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
        <ErrorState title="Failed to load candidate details" onRetry={() => refetch()} action={<Button variant="ghost" onClick={handleBack}>Go back</Button>} />
      </div>
    );
  }

  const { profile, screening, interview, self_reported_contact: selfReported } = data;
  const hasScoredEvaluation = !!screening && screening.decision !== 'PRE_SCREENED_OUT';
  const showStatusBanner = !screening || screening.decision === 'PRE_SCREENED_OUT';
  const leadEvidence = screening?.evidence?.[0];
  const experience: Record<string, unknown>[] = Array.isArray(profile?.experience) ? profile.experience : [];
  const education: Record<string, unknown>[] = Array.isArray(profile?.education) ? profile.education : [];
  const text = (v: unknown) => (typeof v === 'string' && v.trim() ? v : undefined);
  const years = profile?.total_experience_years;

  return (
    <div className="mx-auto grid max-w-6xl gap-x-0 gap-y-10 lg:grid-cols-[19rem_minmax(0,1fr)] lg:grid-rows-[auto_1fr]">
      {/* LEFT, top: identity, contact, resume, decision */}
      <div className="space-y-7 lg:col-start-1 lg:row-start-1 lg:pr-8">
        <div>
          <Button variant="ghost" size="sm" onClick={handleBack} className="-ml-2.5 mb-4">
            <ArrowLeft size={14} aria-hidden="true" /> Back
          </Button>
          <div className="flex items-center gap-4">
            <span
              aria-hidden="true"
              className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary-subtle-bg)] text-lg font-semibold text-[var(--color-primary-subtle-text)]"
            >
              {getInitials(profile?.name)}
            </span>
            <div className="min-w-0">
              <h1 className="text-page-title break-words text-2xl leading-tight">{name}</h1>
            </div>
          </div>
          <p className="text-body mt-3">
            Applied for{' '}
            <Link to={`/jobs/${jobId}`} className="focus-ring rounded font-medium text-[var(--text-primary)] hover:underline">
              {job?.title || 'this job'}
            </Link>
            {typeof years === 'number' && <> · {years} yr{years === 1 ? '' : 's'} experience</>}
          </p>
          <div className="mt-3">
            <DecisionStatus candidate={{ status: screening?.status ?? data.status, decision: screening?.decision, evaluation_failed: screening?.evaluation_failed }} />
          </div>
        </div>

        <Section title="Contact">
          <dl className="space-y-2.5 text-sm">
            <div className="flex items-start gap-2.5">
              <dt className="sr-only">Email</dt>
              <Mail size={15} aria-hidden="true" className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />
              <dd className="min-w-0 break-all text-[var(--text-primary)]">
                {profile?.email ? <a href={`mailto:${profile.email}`} className="focus-ring rounded hover:underline">{profile.email}</a> : <span className="text-[var(--text-tertiary)]">No email extracted</span>}
              </dd>
            </div>
            <div className="flex items-start gap-2.5">
              <dt className="sr-only">Phone</dt>
              <Phone size={15} aria-hidden="true" className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />
              <dd className="text-[var(--text-primary)]">{profile?.phone || <span className="text-[var(--text-tertiary)]">No phone extracted</span>}</dd>
            </div>
          </dl>
        </Section>

        {selfReported && (
          <Section
            title="Applied via public link"
            icon={<Inbox size={13} />}
            action={<Badge variant="warning" title="Typed by the candidate into the apply form - not verified, and not part of the extracted profile.">Unverified</Badge>}
          >
            <dl className="space-y-2 text-sm">
              <div><dt className="text-eyebrow">Name</dt><dd className="break-words text-[var(--text-primary)]">{selfReported.name}</dd></div>
              <div><dt className="text-eyebrow">Email</dt><dd className="break-all text-[var(--text-primary)]">{selfReported.email}</dd></div>
              <div><dt className="text-eyebrow">Phone</dt><dd className="text-[var(--text-primary)]">{selfReported.phone || '—'}</dd></div>
            </dl>
          </Section>
        )}

        <Section title="Actions">
          <div className="space-y-3">
            <DecisionControlBar
              stacked
              decision={screening?.decision}
              isPending={decisionMutation.isPending}
              onDecision={(d) => decisionMutation.mutate({ resumeId, decision: d })}
            />
            <div className="flex flex-col gap-2 border-t border-[var(--border-light)] pt-3">
              {data.filename ? (
                <a
                  href={resumesApi.getResumeFileUrl(resumeId)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="transition-base focus-ring inline-flex h-9 items-center justify-center gap-2 rounded-md border border-[var(--border-strong)] bg-[var(--bg-surface)] px-3.5 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-hover)]"
                >
                  <ExternalLink size={14} aria-hidden="true" /> Original resume
                </a>
              ) : (
                <span className="inline-flex h-9 cursor-not-allowed items-center justify-center gap-2 rounded-md border border-[var(--border-light)] px-3.5 text-sm text-[var(--text-tertiary)]" title="Original resume unavailable">
                  <ExternalLink size={14} aria-hidden="true" className="opacity-50" /> Resume unavailable
                </span>
              )}
              <Button
                variant="secondary"
                onClick={() => addToPool.mutate({ resume_id: resumeId, added_from_job_id: jobId })}
                disabled={addToPool.isPending}
              >
                <PackagePlus size={14} aria-hidden="true" /> Add to Talent Pool
              </Button>
              <LinkButton to={`/interview/${jobId}/${resumeId}`} variant="secondary">Interview workspace</LinkButton>
            </div>
          </div>
        </Section>
      </div>

      {/* LEFT, bottom: notes, timeline, identity (below the evaluation on mobile) */}
      <div className="order-last space-y-7 lg:order-none lg:col-start-1 lg:row-start-2 lg:pr-8">
        <RecruiterNotes key={resumeId} jobId={jobId} resumeId={resumeId} savedNotes={screening?.notes} />
        <CandidateTimeline data={data} />
        {screening?.raw_candidate_id != null && (
          <CandidateIdentityPanel candidateId={screening.raw_candidate_id} applicationsCount={screening.applications_count} />
        )}
      </div>

      {/* RIGHT: evaluation and profile, divided from the sidebar by a hairline */}
      <div className="space-y-9 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:border-l lg:border-[var(--border-light)] lg:pl-10">
        <h2 className="text-section-heading">Detailed AI evaluation</h2>

        {screening?.evaluation_failed && (
          <EvaluationFailedBanner onRetry={() => retryEvaluation.mutate(resumeId)} isPending={retryEvaluation.isPending} />
        )}
        {showStatusBanner && (
          <CandidateStatusBanner
            resumeStatus={screening?.status ?? data.status}
            decision={screening?.decision ?? null}
            errorMessage={screening?.error_message ?? data.error_message ?? null}
          />
        )}

        {hasScoredEvaluation && screening.score != null && (
          <section aria-label="Fit score" className="max-w-lg">
            <FitScore score={screening.score} size="lg" />
            <p className="text-caption tabular mt-3">Semantic match {formatSemantic(screening.semantic_score)}</p>
          </section>
        )}

        {hasScoredEvaluation && (leadEvidence || profile?.summary) && (
          <Section title="AI summary">
            {leadEvidence && <p className="leading-relaxed text-[var(--text-primary)]">{leadEvidence}</p>}
            {profile?.summary && <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">{profile.summary}</p>}
          </Section>
        )}

        {hasScoredEvaluation && <ScreeningAnalysis screening={screening} />}

        {hasScoredEvaluation && (screening.evidence?.length ?? 0) > 0 && (
          <Section title="Evidence"><EvidenceList items={screening.evidence} /></Section>
        )}

        {interview && <InterviewSummary interview={interview} workspaceTo={`/interview/${jobId}/${resumeId}`} />}

        <Section title="Experience" id="experience">
          {experience.length > 0 ? (
            <ol className="divide-y divide-[var(--border-light)]">
              {experience.map((exp, i) => (
                <li key={i} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <p className="font-medium text-[var(--text-primary)]">{text(exp.role) ?? text(exp.title) ?? 'Role not stated'}</p>
                    {(text(exp.duration) ?? text(exp.dates)) && <p className="text-caption tabular">{text(exp.duration) ?? text(exp.dates)}</p>}
                  </div>
                  {text(exp.company) && <p className="text-sm text-[var(--text-secondary)]">{text(exp.company)}</p>}
                  {text(exp.description) && <p className="mt-2 text-sm leading-relaxed text-[var(--text-secondary)]">{text(exp.description)}</p>}
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm italic text-[var(--text-tertiary)]">No experience data extracted</p>
          )}
        </Section>

        <Section title="Education" id="education">
          {education.length > 0 ? (
            <ol className="divide-y divide-[var(--border-light)]">
              {education.map((edu, i) => (
                <li key={i} className="py-3 first:pt-0 last:pb-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-4">
                    <p className="font-medium text-[var(--text-primary)]">{text(edu.degree) ?? 'Degree not stated'}</p>
                    {text(edu.year) && <p className="text-caption tabular">{text(edu.year)}</p>}
                  </div>
                  {text(edu.institution) && <p className="text-sm text-[var(--text-secondary)]">{text(edu.institution)}</p>}
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm italic text-[var(--text-tertiary)]">No education data extracted</p>
          )}
        </Section>

        <Section title="Skills" id="skills">
          <ExtractedSkills profile={profile} limit={40} />
        </Section>

        <OutreachHistory resumeId={resumeId} />
      </div>
    </div>
  );
};
