import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { Mail } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useEmailMessages } from '../hooks/useEmails';
import { OutreachHistory } from '../components/candidate/OutreachHistory';
import { CandidateIdentity } from '../components/candidate/ScreeningCells';
import {
  DataTable, Drawer, DrawerBody, DrawerContent, DrawerHeader, EmptyState, ErrorState, FilterBar, FilterBarSpacer, NativeSelect,
  PageHeader, Pagination, StatTile, StatusDot, type Column,
} from '../components/ui';
import { emailStatusLabel, getEmailStatusBadgeVariant } from '../utils/status';
import { getErrorMessage } from '../utils/errors';
import type { EmailMessageGlobalResponse } from '../types';

const PAGE_SIZE = 20;

type StatQuery = ReturnType<typeof useEmailMessages>;
const stat = (q: StatQuery) => ({ value: q.isError ? undefined : q.data?.total ?? (q.isLoading ? undefined : 0), isLoading: q.isLoading });

export const Outreach = () => {
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [jobId, setJobId] = useState<number | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [detailRow, setDetailRow] = useState<EmailMessageGlobalResponse | null>(null);

  const { data: jobs } = useQuery({ queryKey: queryKeys.jobs(), queryFn: jobsApi.getJobs });

  const allStats = useEmailMessages({ page_size: 1 });
  const sentStats = useEmailMessages({ status: 'SENT', page_size: 1 });
  const pendingStats = useEmailMessages({ status: 'PENDING', page_size: 1 });
  const failedStats = useEmailMessages({ status: 'FAILED', page_size: 1 });
  const blockedStats = useEmailMessages({ status: 'BLOCKED', page_size: 1 });

  const params = { status, job_id: jobId, page, page_size: PAGE_SIZE };
  const { data, isLoading, isFetching, isError, error, refetch } = useEmailMessages(params);

  const filtered = !!(status || jobId);
  const failedTotal = failedStats.data?.total ?? 0;

  const columns: Column<EmailMessageGlobalResponse>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-60',
      cell: (m) => <CandidateIdentity name={m.candidate_name} fallback={`Resume #${m.resume_id}`} />,
    },
    { id: 'job', header: 'Job', hideBelow: 'lg', cell: (m) => <span className="text-sm text-[var(--text-secondary)]">{m.job_title || `Job #${m.job_id}`}</span> },
    {
      id: 'subject',
      header: 'Subject',
      mobile: 'body',
      className: 'min-w-[14rem]',
      cell: (m) => <span className="line-clamp-1 text-sm text-[var(--text-primary)] md:max-w-xs">{m.subject}</span>,
    },
    {
      id: 'status',
      header: 'Status',
      className: 'w-48',
      skeleton: 'badge',
      cell: (m) => <StatusDot variant={getEmailStatusBadgeVariant(m.status)}>{emailStatusLabel(m.status)}</StatusDot>,
    },
    {
      id: 'sent',
      header: 'Sent',
      className: 'w-36',
      cell: (m) => (
        <span className="text-caption whitespace-nowrap">
          {m.sent_at || m.created_at ? formatDistanceToNow(new Date(m.sent_at || m.created_at), { addSuffix: true }) : '—'}
        </span>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader className="mb-6" title="Email & outreach" subtitle="All candidate outreach emails sent across every job." />

      <section aria-label="Outreach totals" className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        <StatTile label="Total" {...stat(allStats)} />
        <StatTile label="Delivered" {...stat(sentStats)} />
        <StatTile label="Pending" {...stat(pendingStats)} />
        <StatTile label="Failed" tone={failedTotal > 0 ? 'danger' : 'default'} {...stat(failedStats)} />
        <StatTile label="Blocked" hint="Not in allowlist" {...stat(blockedStats)} />
      </section>

      <FilterBar className="mb-4">
        <NativeSelect
          aria-label="Filter by status"
          value={status ?? ''}
          onChange={(e) => { setStatus(e.target.value || undefined); setPage(1); }}
        >
          <option value="">All statuses</option>
          {['PENDING', 'SENT', 'SIMULATED', 'FAILED', 'BLOCKED'].map((s) => (
            <option key={s} value={s}>{emailStatusLabel(s)}</option>
          ))}
        </NativeSelect>
        <NativeSelect
          aria-label="Filter by job"
          value={jobId ?? ''}
          onChange={(e) => { setJobId(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
          className="max-w-[16rem]"
        >
          <option value="">All jobs</option>
          {jobs?.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}
        </NativeSelect>
        <FilterBarSpacer />
        {data && <span className="text-caption tabular" aria-live="polite">{data.total} email{data.total === 1 ? '' : 's'}</span>}
      </FilterBar>

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load outreach history" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Outreach emails"
            rows={data?.items ?? []}
            columns={columns}
            getRowId={(m) => m.id}
            isLoading={isLoading && !data}
            isRefreshing={isFetching && !!data}
            onRowClick={(m) => setDetailRow(m)}
            empty={
              <EmptyState
                icon={<Mail size={20} />}
                title={filtered ? 'No emails match these filters' : 'No outreach sent yet'}
                description={filtered ? 'Try a different status or job.' : "Send emails from a job's candidate list to see activity here."}
              />
            }
          />
          {data && data.total > 0 && <Pagination className="mt-4" page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
        </>
      )}

      <Drawer open={!!detailRow} onOpenChange={(open) => { if (!open) setDetailRow(null); }}>
        <DrawerContent>
          <DrawerHeader
            title={detailRow?.candidate_name || `Resume #${detailRow?.resume_id}`}
            description={detailRow?.job_title ? `Outreach for ${detailRow.job_title}` : 'Full outreach history for this candidate.'}
          />
          <DrawerBody>{detailRow && <OutreachHistory resumeId={detailRow.resume_id} />}</DrawerBody>
        </DrawerContent>
      </Drawer>
    </div>
  );
};
