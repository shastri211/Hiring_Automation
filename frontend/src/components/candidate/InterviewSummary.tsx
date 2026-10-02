import { Link } from 'react-router-dom';
import { Mic } from 'lucide-react';
import { Badge, Section, StatusDot } from '../ui';
import { getInterviewStatusBadgeVariant } from '../../utils/status';
import { parseRecommendation } from '../../utils/interviewEvaluation';
import type { Interview, InterviewEvaluationData } from '../../types';

// Evaluation facts worth a row once the interview has actually produced them.
const FACTS: { key: keyof InterviewEvaluationData; label: string }[] = [
  { key: 'years_relevant_experience', label: 'Relevant experience' },
  { key: 'key_skills_mentioned', label: 'Skills mentioned' },
  { key: 'notice_period', label: 'Notice period' },
  { key: 'salary_expectation', label: 'Salary expectation' },
  { key: 'motivation_summary', label: 'Motivation' },
  { key: 'concerns_or_gaps', label: 'Concerns or gaps' },
];

/** The interview's status, recommendation and captured facts — real fields only. */
export const InterviewSummary = ({ interview, workspaceTo }: { interview: Interview; workspaceTo: string }) => {
  const recommendation = parseRecommendation(interview.evaluation?.interview_recommendation);
  const facts = FACTS.map((f) => ({ label: f.label, value: interview.evaluation?.[f.key] })).filter(
    (f): f is { label: string; value: string } => typeof f.value === 'string' && f.value.trim().length > 0
  );

  return (
    <Section
      title="Interview"
      icon={<Mic size={13} />}
      action={
        <Link to={workspaceTo} className="focus-ring rounded text-xs font-medium text-[var(--color-primary-600)] hover:underline">
          Open interview workspace
        </Link>
      }
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <StatusDot variant={getInterviewStatusBadgeVariant(interview.status)}>
          {interview.status.charAt(0) + interview.status.slice(1).toLowerCase().replace(/_/g, ' ')}
        </StatusDot>
        {recommendation && (
          <Badge variant={recommendation.variant} title={recommendation.reason || undefined}>
            Recommendation: {recommendation.label}
          </Badge>
        )}
      </div>
      {recommendation?.reason && <p className="mt-3 text-sm leading-relaxed text-[var(--text-secondary)]">{recommendation.reason}</p>}
      {facts.length > 0 && (
        <dl className="mt-4 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
          {facts.map((f) => (
            <div key={f.label}>
              <dt className="text-eyebrow">{f.label}</dt>
              <dd className="mt-0.5 text-[var(--text-primary)]">{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </Section>
  );
};
