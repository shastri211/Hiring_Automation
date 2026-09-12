import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, Mail, ChevronLeft, ChevronRight } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useEmailMessages } from '../hooks/useEmails';
import { OutreachHistory } from '../components/candidate/OutreachHistory';
import {
  Card, CardContent,
  Badge, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Dialog, DialogContent, DialogTitle, DialogDescription,
} from '../components/ui';
import { getEmailStatusBadgeVariant } from '../utils/status';
import type { EmailMessageGlobalResponse } from '../types';

const PAGE_SIZE = 20;

const StatCard = ({ label, value, isLoading, isError }: { label: string; value?: number; isLoading: boolean; isError: boolean }) => (
  <Card>
    <CardContent className="p-5">
      <div className="text-sm text-[var(--text-secondary)] mb-1">{label}</div>
      {isLoading ? (
        <Loader2 className="w-5 h-5 animate-spin text-[var(--text-tertiary)]" />
      ) : isError ? (
        <div className="text-2xl font-bold text-[var(--text-tertiary)]">—</div>
      ) : (
        <div className="text-2xl font-bold text-[var(--text-primary)]">{value ?? 0}</div>
      )}
    </CardContent>
  </Card>
);

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

  const params = { status, job_id: jobId, page, page_size: PAGE_SIZE };
  const { data, isLoading, isError, error } = useEmailMessages(params);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Mail className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Email &amp; Outreach</h1>
          <p className="text-sm text-[var(--text-secondary)]">All candidate outreach emails sent across every job.</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Sent" value={allStats.data?.total} isLoading={allStats.isLoading} isError={allStats.isError} />
        <StatCard label="Delivered" value={sentStats.data?.total} isLoading={sentStats.isLoading} isError={sentStats.isError} />
        <StatCard label="Pending" value={pendingStats.data?.total} isLoading={pendingStats.isLoading} isError={pendingStats.isError} />
        <StatCard label="Failed" value={failedStats.data?.total} isLoading={failedStats.isLoading} isError={failedStats.isError} />
      </div>

      <div className="flex flex-wrap justify-end gap-3 mb-4">
        <div className="w-48">
          <Select value={status || 'all'} onValueChange={(v) => { setStatus(v === 'all' ? undefined : v); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="All Statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="PENDING">Pending</SelectItem>
              <SelectItem value="SENT">Sent</SelectItem>
              <SelectItem value="FAILED">Failed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-56">
          <Select value={jobId ? String(jobId) : 'all'} onValueChange={(v) => { setJobId(v === 'all' ? undefined : Number(v)); setPage(1); }}>
            <SelectTrigger><SelectValue placeholder="All Jobs" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Jobs</SelectItem>
              {jobs?.map((job) => <SelectItem key={job.id} value={String(job.id)}>{job.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm overflow-hidden">
        {isLoading && !data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            Failed to load outreach history{error instanceof Error ? `: ${error.message}` : '.'}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-20">
            <Mail className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">No outreach sent yet</h3>
            <p className="text-[var(--text-secondary)]">Send emails from a job's candidate list to see activity here.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-6 py-4 font-medium">Candidate</th>
                    <th className="px-6 py-4 font-medium">Job</th>
                    <th className="px-6 py-4 font-medium">Subject</th>
                    <th className="px-6 py-4 font-medium">Status</th>
                    <th className="px-6 py-4 font-medium">Sent</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {data.items.map((msg) => (
                    <tr key={msg.id} className="hover:bg-[var(--bg-hover)] transition-colors cursor-pointer" onClick={() => setDetailRow(msg)}>
                      <td className="px-6 py-4 font-medium text-[var(--text-primary)]">{msg.candidate_name || `Resume #${msg.resume_id}`}</td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">{msg.job_title || `Job #${msg.job_id}`}</td>
                      <td className="px-6 py-4 text-[var(--text-secondary)] max-w-xs truncate">{msg.subject}</td>
                      <td className="px-6 py-4"><Badge variant={getEmailStatusBadgeVariant(msg.status)}>{msg.status}</Badge></td>
                      <td className="px-6 py-4 text-xs text-[var(--text-tertiary)]">
                        {(msg.sent_at || msg.created_at) ? formatDistanceToNow(new Date(msg.sent_at || msg.created_at), { addSuffix: true }) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, data.total)} of {data.total}</span>
              <div className="flex gap-1">
                <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button disabled={page * PAGE_SIZE >= data.total} onClick={() => setPage((p) => p + 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      <Dialog open={!!detailRow} onOpenChange={(open) => { if (!open) setDetailRow(null); }}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogTitle>{detailRow?.candidate_name || `Resume #${detailRow?.resume_id}`}</DialogTitle>
          <DialogDescription>Full outreach history for this candidate.</DialogDescription>
          {detailRow && <OutreachHistory resumeId={detailRow.resume_id} />}
        </DialogContent>
      </Dialog>
    </div>
  );
};
