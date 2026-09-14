import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { ListChecks, Loader2 } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { Badge, Progress } from '../components/ui';
import type { JobBatchOverviewItem } from '../types';

const isLive = (status: string) => status !== 'COMPLETED' && status !== 'FAILED';

export const Processing = () => {
  const navigate = useNavigate();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.batchesOverview(),
    queryFn: jobsApi.getBatchesOverview,
    refetchInterval: (query) => (query.state.data?.some((b) => isLive(b.batch_status)) ? 5000 : false),
  });

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <ListChecks className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Processing</h1>
          <p className="text-sm text-[var(--text-secondary)]">Resume extraction and screening batches, across every job.</p>
        </div>
      </div>

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm overflow-hidden">
        {isLoading ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            Failed to load processing batches{error instanceof Error ? `: ${error.message}` : '.'}
          </div>
        ) : !data || data.length === 0 ? (
          <div className="text-center py-20">
            <ListChecks className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">No batches yet</h3>
            <p className="text-[var(--text-secondary)]">Upload resumes to a job to see processing activity here.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                <tr>
                  <th className="px-6 py-4 font-medium">Job</th>
                  <th className="px-6 py-4 font-medium">Batch</th>
                  <th className="px-6 py-4 font-medium">Status</th>
                  <th className="px-6 py-4 font-medium w-64">Progress</th>
                  <th className="px-6 py-4 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-light)]">
                {data.map((batch) => (
                  <BatchRow key={batch.batch_id} batch={batch} onClick={() => navigate(`/jobs/${batch.job_id}/processing`)} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

const BatchRow = ({ batch, onClick }: { batch: JobBatchOverviewItem; onClick: () => void }) => {
  const done = batch.processed + batch.failed;
  const pct = batch.total > 0 ? Math.min(100, Math.round((done / batch.total) * 100)) : 0;

  return (
    <tr
      className="hover:bg-[var(--bg-hover)] transition-colors cursor-pointer"
      onClick={onClick}
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onClick()}
    >
      <td className="px-6 py-4 font-medium text-[var(--text-primary)]">{batch.job_title}</td>
      <td className="px-6 py-4 text-[var(--text-secondary)]">#{batch.batch_id}</td>
      <td className="px-6 py-4">
        <div className="flex items-center gap-2">
          {isLive(batch.batch_status) && <Loader2 className="w-3.5 h-3.5 text-[var(--color-primary-500)] animate-spin" />}
          <Badge variant={batch.batch_status === 'FAILED' ? 'danger' : batch.batch_status === 'COMPLETED' ? 'success' : 'neutral'}>
            {batch.batch_status}
          </Badge>
        </div>
      </td>
      <td className="px-6 py-4">
        <Progress value={pct} className={batch.failed > 0 ? '[&>div]:bg-red-500' : ''} />
        <div className="flex justify-between mt-1 text-xs text-[var(--text-tertiary)]">
          <span>{done} / {batch.total}{batch.failed > 0 ? ` (${batch.failed} failed)` : ''}</span>
          <span>{pct}%</span>
        </div>
      </td>
      <td className="px-6 py-4 text-xs text-[var(--text-tertiary)]">
        {batch.created_at ? formatDistanceToNow(new Date(batch.created_at), { addSuffix: true }) : '—'}
      </td>
    </tr>
  );
};
