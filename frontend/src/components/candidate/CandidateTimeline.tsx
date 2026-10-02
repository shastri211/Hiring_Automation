import { format } from 'date-fns';
import { Section } from '../ui';
import type { CandidateDetailResponse } from '../../types';

interface TimelineEvent {
  key: string;
  label: string;
  at: string;
}

/**
 * Timeline built ONLY from timestamps the API actually returns for this
 * candidate: the public-link submission, the screening result, and the
 * interview's scheduled/completed times. Emails are listed in Outreach.
 * Renders nothing when there is nothing real to show.
 */
export const CandidateTimeline = ({ data }: { data: CandidateDetailResponse }) => {
  const events: TimelineEvent[] = [];
  const { self_reported_contact: self, screening, interview } = data;

  if (self?.submitted_at) events.push({ key: 'applied', label: 'Applied via public link', at: self.submitted_at });
  // A decision on an unscreened resume creates an empty row - only count a real screening.
  if (screening?.created_at && (screening.score != null || screening.decision === 'PRE_SCREENED_OUT')) {
    events.push({
      key: 'screened',
      label: screening.decision === 'PRE_SCREENED_OUT' ? 'Pre-screened out' : 'AI screening completed',
      at: screening.created_at,
    });
  }
  if (interview?.scheduled_at) events.push({ key: 'sched', label: 'Interview scheduled', at: interview.scheduled_at });
  if (interview?.completed_at) events.push({ key: 'done', label: 'Interview completed', at: interview.completed_at });

  if (events.length === 0) return null;
  events.sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime());

  return (
    <Section title="Timeline">
      <ol className="relative space-y-4 border-l border-[var(--border-strong)] pl-4">
        {events.map((e) => (
          <li key={e.key} className="relative">
            <span
              aria-hidden="true"
              className="absolute -left-[1.3125rem] top-1.5 h-2 w-2 rounded-full border border-[var(--border-input)] bg-[var(--bg-surface)]"
            />
            <p className="text-sm text-[var(--text-primary)]">{e.label}</p>
            <time dateTime={e.at} className="text-caption">{format(new Date(e.at), 'MMM d, yyyy · h:mm a')}</time>
          </li>
        ))}
      </ol>
    </Section>
  );
};
