import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Play, Clock } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { Button } from '../components/ui/Button';
import { Progress, Badge } from '../components/ui';
import type { BadgeVariant } from '../utils/decision';
import type { BatchProgressDetail } from '../types';
import { toast } from 'sonner';

export const JobProcessing = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const jobId = parseInt(id || '0', 10);

  const { data: job } = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });

  const { data: progressData, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.jobProgress(jobId),
    queryFn: () => jobsApi.getJobProgress(jobId),
    refetchInterval: (query) => {
      // Poll every 3 seconds if there are batches and any batch is not COMPLETED/FAILED
      const data = query.state.data;
      if (!data || !data.batches || data.batches.length === 0) return false;
      const hasActive = data.batches.some(
        (b) => b.status !== 'COMPLETED' && b.status !== 'FAILED'
      );
      return hasActive ? 3000 : false;
    },
    staleTime: 0,
  });

  const screenMutation = useMutation({
    mutationFn: () => jobsApi.screenJob(jobId),
    onSuccess: () => {
      // Invalidate to fetch the new PROCESSING batch immediately
      queryClient.invalidateQueries({ queryKey: queryKeys.jobProgress(jobId) });
      toast.success('Screening started. Results will appear as processing completes.');
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Unable to start screening. Please try again.');
    }
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8">
        <div className="bg-red-50 text-red-700 p-4 rounded-lg">
          Error loading progress: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    );
  }

  const batches = progressData?.batches || [];

  if (batches.length === 0) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
          <button onClick={() => navigate('/jobs')} className="hover:text-slate-900 transition-colors">Jobs</button>
          <span>/</span>
          <button onClick={() => navigate(`/jobs/${id}`)} className="hover:text-slate-900 transition-colors">{job?.title || 'Job'}</button>
          <span>/</span>
          <span className="text-slate-900 font-medium">Processing</span>
        </div>
        <div className="text-center py-24 bg-slate-50 border border-slate-200 rounded-xl">
          <Clock className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">No batches yet</h3>
          <p className="text-slate-500 mb-6">Upload resumes and start screening to see progress here.</p>
          <Button onClick={() => navigate(`/jobs/${id}/upload`)}>Upload Resumes</Button>
        </div>
      </div>
    );
  }

  // Calculate totals across all batches to determine if we can screen
  const totalReady = batches.reduce((sum, b) => sum + (b.completed || 0), 0);
  const totalScreened = batches.reduce((sum, b) => sum + (b.shortlisted || 0) + (b.review || 0) + (b.rejected || 0) + (b.pre_screened_out || 0), 0);
  const unScreenedCount = Math.max(0, totalReady - totalScreened);
  const hasRunningBatch = batches.some(b => b.status === 'PROCESSING');

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <button onClick={() => navigate('/jobs')} className="hover:text-slate-900 transition-colors">Jobs</button>
        <span>/</span>
        <button onClick={() => navigate(`/jobs/${id}`)} className="hover:text-slate-900 transition-colors">Job #{id}</button>
        <span>/</span>
        <span className="text-slate-900 font-medium">Processing</span>
      </div>

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 mb-1">Processing</h1>
          <p className="text-slate-500">Monitor extraction and screening progress.</p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => navigate(`/jobs/${id}/upload`)}>
            Upload Resumes
          </Button>
          {unScreenedCount > 0 && (
            <Button 
              onClick={() => screenMutation.mutate()} 
              disabled={hasRunningBatch || screenMutation.isPending}
            >
              {hasRunningBatch || screenMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Screening...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Start Screening ({unScreenedCount})
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-4">
        {batches.map((b) => (
          <BatchCard key={b.batch_id} batch={b} jobId={jobId} onNavigate={(path) => navigate(path)} />
        ))}
      </div>
    </div>
  );
};

const BatchCard = ({ batch, jobId, onNavigate }: { batch: BatchProgressDetail, jobId: number, onNavigate: (path: string) => void }) => {
  const isScreening = (batch.total === 0);
  const isLive = batch.status !== 'COMPLETED' && batch.status !== 'FAILED';
  
  const statusLabel = batch.status === 'PROCESSING' 
    ? (isScreening ? 'SCREENING' : 'PROCESSING') 
    : (batch.status === 'COMPLETED' ? (isScreening ? 'SCREENING COMPLETE' : 'READY') : batch.status);

  const getBorderColor = () => {
    if (batch.status === 'COMPLETED') return isScreening ? 'border-green-200' : 'border-blue-200';
    if (batch.status === 'FAILED') return 'border-red-200';
    return 'border-slate-200';
  };

  // Screening runs and upload batches use different color semantics for the
  // same underlying status (a "COMPLETED" screening run is success/green; a
  // "COMPLETED" upload batch is "READY" and stays primary/indigo like today).
  const statusBadgeVariant: BadgeVariant = batch.status === 'FAILED'
    ? 'danger'
    : batch.status === 'COMPLETED'
      ? (isScreening ? 'success' : 'primary')
      : (isScreening ? 'primary' : 'neutral');

  if (isScreening) {
    return (
      <div className={`bg-white border rounded-xl p-5 shadow-sm ${getBorderColor()}`}>
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="font-semibold text-slate-900">Screening Run #{batch.batch_id}</h3>
          </div>
          <div className="flex items-center gap-2">
            {isLive && <Loader2 className="w-4 h-4 text-[var(--color-primary-500)] animate-spin" />}
            <Badge variant={statusBadgeVariant}>{statusLabel}</Badge>
          </div>
        </div>
        <div className="flex gap-4">
          <StatPill val={batch.shortlisted || 0} lbl="Shortlist" color="text-green-600" bg="bg-green-50" />
          <StatPill val={batch.review || 0} lbl="Review" color="text-amber-600" bg="bg-amber-50" />
          <StatPill val={batch.rejected || 0} lbl="Rejected" color="text-red-600" bg="bg-red-50" />
          {(batch.pre_screened_out ?? 0) > 0 && (
            <StatPill val={batch.pre_screened_out || 0} lbl="Pre-screened Out" color="text-slate-600" bg="bg-slate-100" />
          )}
        </div>
        {batch.status === 'COMPLETED' && (
          <div className="mt-4">
            <Button variant="ghost" size="sm" onClick={() => onNavigate(`/jobs/${jobId}/candidates`)}>
              View Results &rarr;
            </Button>
          </div>
        )}
      </div>
    );
  }

  // Upload Batch
  const done = (batch.completed || 0) + (batch.failed || 0);
  const total = batch.total || 0;
  const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;

  return (
    <div className={`bg-white border rounded-xl p-5 shadow-sm ${getBorderColor()}`}>
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-semibold text-slate-900">Upload Batch #{batch.batch_id}</h3>
        </div>
        <div className="flex items-center gap-2">
          {isLive && <Loader2 className="w-4 h-4 text-[var(--color-primary-500)] animate-spin" />}
          <Badge variant={statusBadgeVariant}>{statusLabel}</Badge>
        </div>
      </div>
      
      <div className="mb-4">
        <Progress value={pct} className={batch.status === 'FAILED' ? '[&>div]:bg-red-500' : ''} />
        <div className="flex justify-between mt-2 text-xs text-slate-500 font-medium">
          <span>{done} / {total} resumes</span>
          <span>{pct}%</span>
        </div>
      </div>

      <div className="flex gap-4">
        <StatPill val={total} lbl="Total" color="text-slate-700" bg="bg-slate-50" />
        <StatPill val={batch.processing || 0} lbl="Processing" color="text-[var(--color-primary-600)]" bg="bg-[var(--color-primary-50)]" />
        <StatPill val={batch.completed || 0} lbl="Ready" color="text-emerald-600" bg="bg-emerald-50" />
        <StatPill val={batch.failed || 0} lbl="Failed" color="text-red-600" bg="bg-red-50" />
      </div>
    </div>
  );
};

const StatPill = ({ val, lbl, color, bg }: { val: number, lbl: string, color: string, bg: string }) => (
  <div className={`flex flex-col items-center px-4 py-2 rounded-lg ${bg}`}>
    <span className={`text-xl font-bold ${color}`}>{val}</span>
    <span className="text-xs font-medium text-slate-600">{lbl}</span>
  </div>
);
