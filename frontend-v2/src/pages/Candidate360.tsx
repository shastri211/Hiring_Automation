import { useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, Briefcase, GraduationCap, PackagePlus, Pencil, Check, X, Undo2, Users2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { jobsApi } from '../api/jobs';
import { resumesApi } from '../api/resumes';
import { queryKeys } from '../api/queryKeys';
import { useDecisionMutation, useRetryEvaluation } from '../hooks/useDecisionMutation';
import { useAddToTalentPool } from '../hooks/useTalentPool';
import { useCandidate, useUpdateCandidateName, useUnmergeCandidate } from '../hooks/useCandidateIdentity';
import { useConfirm } from '../hooks/useConfirm';
import { Button } from '../components/ui/Button';
import { Spinner, PageHeader, Input, Badge } from '../components/ui';
import { parseRecommendation } from '../utils/interviewEvaluation';
import {
  ScoreVisualizer,
  DecisionControlBar,
  ExtractedSkills,
  ScreeningAnalysis,
  EvaluationFailedBanner
} from '../components/candidate/CandidateComponents';
import { OutreachHistory } from '../components/candidate/OutreachHistory';

const CandidateIdentityCard = ({ candidateId, applicationsCount }: { candidateId: number; applicationsCount?: number | null }) => {
  const { data: candidate, isLoading } = useCandidate(candidateId);
  const updateName = useUpdateCandidateName();
  const unmerge = useUnmergeCandidate();
  const confirm = useConfirm();
  const [isEditing, setIsEditing] = useState(false);
  const [nameInput, setNameInput] = useState('');

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
    <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] shadow-[var(--shadow-sm)] p-6">
      <h3 className="text-sm font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-2">
        <Users2 className="w-4 h-4 text-[var(--text-tertiary)]" /> Candidate Identity
      </h3>

      {candidate.merged_into_id != null && (
        <div className="mb-3 p-3 rounded-lg bg-[var(--color-warning-subtle-bg)] text-[var(--color-warning-subtle-text)] text-xs">
          <p className="mb-2">
            This candidate record was merged into{' '}
            <span className="font-medium">{candidate.merged_into_name || `candidate #${candidate.merged_into_id}`}</span>.
          </p>
          <Button variant="secondary" onClick={handleUndoMerge} disabled={unmerge.isPending} className="flex items-center gap-1.5 h-7 px-2.5 text-xs">
            <Undo2 className="w-3.5 h-3.5" /> Undo Merge
          </Button>
        </div>
      )}

      <div className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wide mb-1">Display name</div>
      {isEditing ? (
        <div className="flex items-center gap-2">
          <Input
            autoFocus
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Leave blank to use extracted/derived name"
            className="h-8 text-sm"
          />
          <button onClick={saveName} disabled={updateName.isPending} className="text-[var(--color-success-600)] hover:opacity-75 shrink-0" title="Save">
            <Check className="w-4 h-4" />
          </button>
          <button onClick={() => setIsEditing(false)} className="text-[var(--text-tertiary)] hover:opacity-75 shrink-0" title="Cancel">
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="text-sm text-[var(--text-primary)]">{candidate.canonical_name || <em className="text-[var(--text-tertiary)] not-italic">Using extracted/derived name</em>}</span>
          <button onClick={startEdit} className="text-[var(--text-tertiary)] hover:text-[var(--color-primary-600)]" title="Edit display name">
            <Pencil className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {applicationsCount != null && (
        <p className="mt-3 pt-3 border-t border-[var(--border-light)] text-xs text-[var(--text-secondary)]">
          Applied to {applicationsCount} job{applicationsCount === 1 ? '' : 's'} total.
        </p>
      )}
    </div>
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

  const decisionMutation = useDecisionMutation(jobId);
  const retryEvaluation = useRetryEvaluation(jobId);
  const addToPool = useAddToTalentPool();
  const interviewRecommendation = parseRecommendation(data?.interview?.evaluation?.interview_recommendation);

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
      <div className="flex-1 flex items-center justify-center p-8">
        <Spinner size={32} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex-1 p-8">
        <div className="bg-[var(--color-danger-subtle-bg)] text-[var(--color-danger-subtle-text)] p-4 rounded-lg flex items-center justify-between gap-4">
          <span>Failed to load candidate details.</span>
          <Button variant="secondary" onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-[var(--bg-app)] overflow-hidden">
      {/* Header */}
      <div className="bg-[var(--bg-surface)] border-b border-[var(--border-light)] px-8 py-4 shrink-0">
        <PageHeader
          size="section"
          leading={
            <button
              onClick={handleBack}
              className="transition-base focus-ring p-2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] rounded-lg"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          }
          title={data.profile?.name || `Candidate #${resumeId}`}
          subtitle={<>{data.profile?.email} &bull; {data.profile?.phone || 'No phone provided'}</>}
          actions={
          <>
          {data.filename ? (
            <a
              href={resumesApi.getResumeFileUrl(resumeId)}
              target="_blank"
              rel="noopener noreferrer"
              className="transition-base focus-ring flex items-center gap-2 px-4 py-2 text-sm font-medium text-[var(--text-secondary)] bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-lg hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            >
              <ExternalLink className="w-4 h-4" /> Original Resume
            </a>
          ) : (
            <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-[var(--text-tertiary)] bg-[var(--bg-app)] border border-[var(--border-light)] rounded-lg cursor-not-allowed" title="Original resume unavailable">
              <ExternalLink className="w-4 h-4 opacity-50" /> Original Resume Unavailable
            </span>
          )}
          <Button
            variant="secondary"
            onClick={() => addToPool.mutate({ resume_id: resumeId, added_from_job_id: jobId })}
            disabled={addToPool.isPending}
            className="flex items-center gap-2"
          >
            <PackagePlus className="w-4 h-4" /> Add to Talent Pool
          </Button>
          {interviewRecommendation && (
            <Badge variant={interviewRecommendation.variant} title={interviewRecommendation.reason || undefined}>
              Interview: {interviewRecommendation.label}
            </Badge>
          )}
          <Link to={`/interview/${jobId}/${resumeId}`}>
            <Button>Interview Workspace</Button>
          </Link>
          </>
          }
        />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-7xl mx-auto">
          <div className="mb-6">
            <DecisionControlBar
              decision={data.screening?.decision}
              isPending={decisionMutation.isPending}
              onDecision={(d) => decisionMutation.mutate({ resumeId, decision: d })}
            />
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Left Column: Profile Data */}
            <div className="xl:col-span-2 space-y-6">
              <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border-light)] shadow-[var(--shadow-sm)] p-6" id="profile">
                <h2 className="text-card-title mb-6">Profile Summary</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-8">
                  <div id="experience">
                    <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3 flex items-center gap-2">
                      <Briefcase className="w-4 h-4" /> Experience
                    </h3>
                    <div className="space-y-4">
                      {Array.isArray(data.profile?.experience) && data.profile.experience.length > 0 ? (
                        data.profile.experience.map((exp: any, i: number) => (
                          <div key={i}>
                            <div className="font-medium text-[var(--text-primary)]">{exp.title || 'Unknown Title'}</div>
                            <div className="text-sm text-[var(--text-secondary)]">{exp.company || 'Unknown Company'}</div>
                            <div className="text-xs text-[var(--text-tertiary)] mt-1">{exp.dates || ''}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-[var(--text-tertiary)] italic">No experience data extracted</div>
                      )}
                    </div>
                  </div>
                  <div id="education">
                    <h3 className="text-sm font-medium text-[var(--text-secondary)] mb-3 flex items-center gap-2">
                      <GraduationCap className="w-4 h-4" /> Education
                    </h3>
                    <div className="space-y-4">
                      {Array.isArray(data.profile?.education) && data.profile.education.length > 0 ? (
                        data.profile.education.map((edu: any, i: number) => (
                          <div key={i}>
                            <div className="font-medium text-[var(--text-primary)]">{edu.degree || 'Unknown Degree'}</div>
                            <div className="text-sm text-[var(--text-secondary)]">{edu.institution || 'Unknown Institution'}</div>
                            <div className="text-xs text-[var(--text-tertiary)] mt-1">{edu.year || ''}</div>
                          </div>
                        ))
                      ) : (
                        <div className="text-sm text-[var(--text-tertiary)] italic">No education data extracted</div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="border-t border-[var(--border-light)] pt-6" id="skills">
                  <ExtractedSkills profile={data.profile} />
                </div>
              </div>

              <OutreachHistory resumeId={resumeId} />
            </div>

            {/* Right Column: AI Screening */}
            <div className="xl:col-span-1">
              <div className="space-y-6 sticky top-0 pb-8">
                {data.screening?.raw_candidate_id != null && (
                  <CandidateIdentityCard
                    candidateId={data.screening.raw_candidate_id}
                    applicationsCount={data.screening.applications_count}
                  />
                )}
                {data.screening?.evaluation_failed && (
                  <EvaluationFailedBanner
                    onRetry={() => retryEvaluation.mutate(resumeId)}
                    isPending={retryEvaluation.isPending}
                  />
                )}
                <ScoreVisualizer screening={data.screening} />
                <ScreeningAnalysis screening={data.screening} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
