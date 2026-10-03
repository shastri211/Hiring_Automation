import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useFunnel, useDecisionBreakdown, useThroughput, useJobVolume, useTimeInStage } from '../hooks/useAnalytics';
import { Card, DataTable, FilterBar, FilterBarSpacer, NativeSelect, PageHeader, PanelBody, PanelHeader, StatTile, type Column } from '../components/ui';
import { chart } from '../components/charts/chartTheme';
import { getDecisionBadgeVariant } from '../utils/decision';
import { decisionLabel, formatDurationSeconds } from '../utils/format';
import type { JobVolumeItem } from '../types';

const DECISION_FILL = {
  success: chart.success, warning: chart.warning, danger: chart.danger, primary: chart.primary, neutral: chart.neutral,
};

// Category tick that wraps onto a second line instead of letting Recharts drop
// overlapping labels - every decision label must stay readable at narrow widths.
const WrappedTick = ({ x, y, payload }: { x?: number; y?: number; payload?: { value: string } }) => {
  const words = String(payload?.value ?? '').split(/ |(?<=-)/);
  return (
    <text x={x} y={y} textAnchor="middle" style={chart.axisSmall}>
      {words.map((word, i) => (
        <tspan key={`${word}-${i}`} x={x} dy={i === 0 ? '0.9em' : '1.15em'}>{word}</tspan>
      ))}
    </text>
  );
};

const EmptyNote = ({ children }: { children: string }) => (
  <p className="text-body px-5 py-10 text-center">{children}</p>
);

export const Analytics = () => {
  const [jobId, setJobId] = useState<number | undefined>(undefined);

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const funnelQuery = useFunnel(jobId);
  const decisionsQuery = useDecisionBreakdown(jobId);
  const throughputQuery = useThroughput(30, jobId);
  const jobVolumeQuery = useJobVolume();
  const timeInStageQuery = useTimeInStage(jobId);

  const funnelData = useMemo(() => {
    const f = funnelQuery.data;
    if (!f) return [];
    return [
      { stage: 'Uploaded', count: f.uploaded },
      { stage: 'Processed', count: f.processed },
      { stage: 'Screened', count: f.screened },
      { stage: 'Shortlisted', count: f.shortlisted },
      { stage: 'Interviewed', count: f.interviewed },
      { stage: 'Completed', count: f.completed },
    ];
  }, [funnelQuery.data]);

  const decisionData = useMemo(
    () => (decisionsQuery.data?.items || []).map((d) => ({ key: d.decision ?? 'none', label: decisionLabel(d.decision), count: d.count, variant: getDecisionBadgeVariant(d.decision) })),
    [decisionsQuery.data]
  );

  const throughputData = useMemo(
    () => (throughputQuery.data?.items || []).map((p) => ({ date: p.date, count: p.count })),
    [throughputQuery.data]
  );

  const time = timeInStageQuery.data;
  const timeEmpty = !time || (time.resume_to_screened_seconds_approx == null && time.screened_to_interview_seconds_approx == null);

  const volumeColumns: Column<JobVolumeItem>[] = [
    { id: 'job', header: 'Job', mobile: 'title', cell: (i) => <span className="text-sm font-medium text-[var(--text-primary)]">{i.job_title}</span> },
    { id: 'count', header: 'Resumes', align: 'right', className: 'w-32', cell: (i) => <span className="tabular text-sm text-[var(--text-secondary)]">{i.resume_count}</span> },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader className="mb-6" title="Analytics" subtitle="Pipeline health across your hiring funnel." />

      <FilterBar className="mb-6">
        <NativeSelect
          aria-label="Filter by job"
          value={jobId ?? ''}
          onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : undefined)}
          className="max-w-[18rem]"
        >
          <option value="">All jobs</option>
          {jobs?.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
        </NativeSelect>
        <FilterBarSpacer />
      </FilterBar>

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <PanelHeader title="Hiring funnel" />
          <PanelBody
            isLoading={funnelQuery.isLoading}
            isError={funnelQuery.isError}
            onRetry={() => funnelQuery.refetch()}
            isEmpty={funnelData.every((d) => d.count === 0)}
            empty={<EmptyNote>No resumes processed yet for this filter.</EmptyNote>}
            rows={5}
          >
            <div className="p-5" role="img" aria-label={`Hiring funnel: ${funnelData.map((d) => `${d.stage} ${d.count}`).join(', ')}`}>
              <div style={{ width: '100%', height: 280 }}>
                <ResponsiveContainer>
                  <BarChart data={funnelData} layout="vertical" margin={{ left: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={chart.axis} axisLine={chart.axisLine} tickLine={false} />
                    <YAxis type="category" dataKey="stage" width={86} tick={chart.axis} axisLine={chart.axisLine} tickLine={false} />
                    <Tooltip {...chart.tooltip} />
                    <Bar dataKey="count" fill={chart.primary} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </PanelBody>
        </Card>

        <Card>
          <PanelHeader title="Decision breakdown" />
          <PanelBody
            isLoading={decisionsQuery.isLoading}
            isError={decisionsQuery.isError}
            onRetry={() => decisionsQuery.refetch()}
            isEmpty={decisionData.length === 0}
            empty={<EmptyNote>No screening decisions recorded yet for this filter.</EmptyNote>}
            rows={5}
          >
            <div className="p-5" role="img" aria-label={`Decisions: ${decisionData.map((d) => `${d.label} ${d.count}`).join(', ')}`}>
              <div style={{ width: '100%', height: 280 }}>
                <ResponsiveContainer>
                  <BarChart data={decisionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                    <XAxis dataKey="label" tick={<WrappedTick />} interval={0} height={56} axisLine={chart.axisLine} tickLine={false} />
                    <YAxis allowDecimals={false} tick={chart.axis} axisLine={false} tickLine={false} />
                    <Tooltip {...chart.tooltip} />
                    <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                      {decisionData.map((d) => <Cell key={d.key} fill={DECISION_FILL[d.variant]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </PanelBody>
        </Card>
      </div>

      <Card className="mb-6">
        <PanelHeader title="Screening throughput, last 30 days" />
        <PanelBody
          isLoading={throughputQuery.isLoading}
          isError={throughputQuery.isError}
          onRetry={() => throughputQuery.refetch()}
          isEmpty={throughputData.length === 0 || throughputData.every((d) => d.count === 0)}
          empty={<EmptyNote>No screening activity in the last 30 days for this filter.</EmptyNote>}
          rows={4}
        >
          <div className="p-5" role="img" aria-label={`Candidates screened per day over the last 30 days: ${throughputData.reduce((a, d) => a + d.count, 0)} in total`}>
            <div style={{ width: '100%', height: 240 }}>
              <ResponsiveContainer>
                <LineChart data={throughputData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                  <XAxis dataKey="date" tick={chart.axisSmall} axisLine={chart.axisLine} tickLine={false} minTickGap={24} />
                  <YAxis allowDecimals={false} tick={chart.axis} axisLine={false} tickLine={false} />
                  <Tooltip {...chart.tooltip} />
                  <Line type="monotone" dataKey="count" stroke={chart.primary} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </PanelBody>
      </Card>

      <section aria-label="Average time in stage" className="mb-6">
        <h2 className="text-eyebrow mb-3">Average time in stage <span className="normal-case tracking-normal">(approximate)</span></h2>
        {timeInStageQuery.isError ? (
          <p className="text-body">Failed to load stage timings.</p>
        ) : timeEmpty && !timeInStageQuery.isLoading ? (
          <p className="text-body">Not enough completed transitions yet for this filter.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatTile
              label="Upload → screened"
              isLoading={timeInStageQuery.isLoading}
              value={time?.resume_to_screened_seconds_approx != null ? formatDurationSeconds(time.resume_to_screened_seconds_approx) : undefined}
            />
            <StatTile
              label="Screened → interview scheduled"
              isLoading={timeInStageQuery.isLoading}
              value={time?.screened_to_interview_seconds_approx != null ? formatDurationSeconds(time.screened_to_interview_seconds_approx) : undefined}
            />
          </div>
        )}
      </section>

      <section aria-label="Volume by job">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-eyebrow">Volume by job</h2>
          <p className="text-caption">Across all jobs — not affected by the job filter above.</p>
        </div>
        {jobVolumeQuery.isError ? (
          <p className="text-body">Failed to load job volume.</p>
        ) : (
          <DataTable
            aria-label="Resumes per job"
            rows={jobVolumeQuery.data?.items ?? []}
            columns={volumeColumns}
            getRowId={(i) => i.job_id}
            isLoading={jobVolumeQuery.isLoading}
            skeletonRows={3}
            empty={<p className="text-body px-5 py-8 text-center">No jobs with resumes yet.</p>}
          />
        )}
      </section>
    </div>
  );
};
