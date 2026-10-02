import type { FunnelResponse } from '../../types';

/**
 * FunnelBars — the six pipeline stages as labeled horizontal bars, scaled to
 * the largest stage. Shared by the Dashboard (org-wide) and Job Workspace
 * (job-scoped); both feed it the existing /analytics/funnel response.
 */
export const FunnelBars = ({ funnel }: { funnel: FunnelResponse }) => {
  const rows = [
    { label: 'Uploaded', count: funnel.uploaded },
    { label: 'Processed', count: funnel.processed },
    { label: 'Screened', count: funnel.screened },
    { label: 'Shortlisted', count: funnel.shortlisted },
    { label: 'Interviewed', count: funnel.interviewed },
    { label: 'Interview completed', count: funnel.completed },
  ];
  const max = Math.max(...rows.map((r) => r.count), 1);

  return (
    <ol className="space-y-3">
      {rows.map((row) => (
        <li key={row.label} className="grid grid-cols-[8.5rem_1fr_3rem] items-center gap-3 text-sm sm:grid-cols-[10rem_1fr_3.5rem]">
          <span className="truncate text-[var(--text-secondary)]">{row.label}</span>
          <div className="h-2 rounded-sm bg-[var(--bg-hover)]" role="presentation">
            <div className="h-2 rounded-sm bg-[var(--color-primary-600)]" style={{ width: `${(row.count / max) * 100}%` }} />
          </div>
          <span className="tabular text-right font-medium text-[var(--text-primary)]">{row.count}</span>
        </li>
      ))}
    </ol>
  );
};
