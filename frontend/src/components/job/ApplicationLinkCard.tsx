import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Link2, Copy, RefreshCw, XCircle } from 'lucide-react';
import { api } from '../../api';
import { queryKeys } from '../../api/queryKeys';
import { Badge, Button } from '../ui';
import { useConfirm } from '../../hooks/useConfirm';
import type { ApiError, Job } from '../../types';

// Recruiter control for a job's public candidate apply link
// (app/api/jobs.py application-link endpoints). The token is the link's only
// credential: closing clears it and rotating replaces it, so an old link
// simply stops resolving.
export const ApplicationLinkCard = ({ job }: { job: Job }) => {
  const queryClient = useQueryClient();
  const confirm = useConfirm();

  const onDone = (updated: Job) => {
    queryClient.setQueryData(queryKeys.job(job.id), updated);
    queryClient.invalidateQueries({ queryKey: queryKeys.job(job.id) });
  };
  const onError = (error: ApiError) => toast.error(error.message || 'Could not update the application link.');

  const openMutation = useMutation({ mutationFn: () => api.jobs.openApplicationLink(job.id), onSuccess: onDone, onError });
  const rotateMutation = useMutation({ mutationFn: () => api.jobs.rotateApplicationLink(job.id), onSuccess: onDone, onError });
  const closeMutation = useMutation({ mutationFn: () => api.jobs.closeApplicationLink(job.id), onSuccess: onDone, onError });
  const pending = openMutation.isPending || rotateMutation.isPending || closeMutation.isPending;

  const isOpen = !!job.application_token;
  const jobAccepting = !job.status || job.status === 'ACTIVE';
  // Falls back to this frontend's own origin when the backend has no
  // PUBLIC_APP_BASE_URL configured.
  const url = job.application_url || (isOpen ? `${window.location.origin}/apply/${job.application_token}` : null);

  const copy = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      toast.success('Application link copied.');
    } catch {
      toast.error('Could not copy - select the link and copy it manually.');
    }
  };

  return (
    <section>
      <h3 className="text-card-title mb-4 pb-2 border-b border-[var(--border-light)] flex items-center gap-2">
        <Link2 size={16} /> Public Application Link
        <Badge variant={isOpen ? (jobAccepting ? 'success' : 'warning') : 'neutral'} className="ml-auto">
          {isOpen ? (jobAccepting ? 'Open' : 'Paused') : 'Closed'}
        </Badge>
      </h3>

      {!isOpen ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[var(--text-secondary)]">
            Let candidates apply directly with their resume. Applications join this job&apos;s pool and are
            screened the next time you run screening.
          </p>
          <Button variant="secondary" onClick={() => openMutation.mutate()} disabled={pending} className="self-start">
            <Link2 size={16} className="mr-2" /> {openMutation.isPending ? 'Opening...' : 'Open applications'}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {!jobAccepting && (
            <p className="text-xs text-[var(--color-warning-subtle-text)]">
              This job isn&apos;t active, so the link currently shows candidates a &quot;closed&quot; page.
            </p>
          )}
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={url ?? ''}
              onFocus={(e) => e.currentTarget.select()}
              aria-label="Public application link"
              className="flex-1 min-w-0 rounded-md border border-[var(--border-light)] bg-[var(--bg-app)] px-2 py-1.5 text-xs text-[var(--text-secondary)]"
            />
            <Button variant="secondary" size="sm" onClick={copy} disabled={!url} title="Copy link">
              <Copy size={14} />
            </Button>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={pending}
              onClick={async () => {
                const ok = await confirm({
                  title: 'Rotate application link?',
                  description: 'A new link is generated and the current one stops working immediately. Anyone with the old link will see "not found".',
                  confirmLabel: 'Rotate link',
                });
                if (ok) rotateMutation.mutate();
              }}
            >
              <RefreshCw size={14} className="mr-1.5" /> {rotateMutation.isPending ? 'Rotating...' : 'Rotate'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={pending}
              className="text-[var(--color-danger-600)] hover:text-[var(--color-danger-600)] hover:bg-[var(--color-danger-subtle-bg)]"
              onClick={async () => {
                const ok = await confirm({
                  title: 'Close applications?',
                  description: 'The current link stops working immediately. Applications already received are kept. You can open a new link later.',
                  confirmLabel: 'Close applications',
                  danger: true,
                });
                if (ok) closeMutation.mutate();
              }}
            >
              <XCircle size={14} className="mr-1.5" /> {closeMutation.isPending ? 'Closing...' : 'Close'}
            </Button>
          </div>
        </div>
      )}
    </section>
  );
};
