import type { BadgeVariant } from './decision';

/**
 * Interview status -> Badge variant. Parallel to decision.ts::getDecisionBadgeVariant
 * but for the Interview.status enum (PENDING | SCHEDULED | IN_PROGRESS | COMPLETED |
 * FAILED | RESCHEDULE_PENDING | NO_SHOW | DECLINED).
 */
export function getInterviewStatusBadgeVariant(status?: string | null): BadgeVariant {
  switch (status) {
    case 'COMPLETED':
      return 'success';
    case 'IN_PROGRESS':
      return 'warning';
    case 'SCHEDULED':
      return 'primary';
    case 'FAILED':
      return 'danger';
    case 'RESCHEDULE_PENDING':
      return 'warning';
    case 'NO_SHOW':
      return 'danger';
    case 'DECLINED':
      return 'neutral';
    case 'PENDING':
    default:
      return 'neutral';
  }
}

/**
 * EmailMessage status -> Badge variant.
 */
export function getEmailStatusBadgeVariant(status?: string | null): BadgeVariant {
  switch (status) {
    case 'SENT':
      return 'success';
    case 'PENDING':
    case 'SIMULATED':
      return 'warning';
    case 'FAILED':
      return 'danger';
    case 'BLOCKED':
      return 'neutral';
    default:
      return 'neutral';
  }
}

/**
 * Job.status (ACTIVE | PAUSED | ARCHIVED; absent on older rows = ACTIVE) -> StatusDot/Badge variant.
 */
export function getJobStatusVariant(status?: string | null): BadgeVariant {
  switch (status) {
    case 'PAUSED':
      return 'warning';
    case 'ARCHIVED':
      return 'neutral';
    default:
      return 'success';
  }
}

export function jobStatusLabel(status?: string | null): string {
  const s = status || 'ACTIVE';
  return s.charAt(0) + s.slice(1).toLowerCase();
}

/** A batch is still running unless it reached a terminal state. */
export const isBatchLive = (status: string) => status !== 'COMPLETED' && status !== 'FAILED';

export function getBatchStatusVariant(status: string): BadgeVariant {
  if (status === 'FAILED') return 'danger';
  if (status === 'COMPLETED') return 'success';
  return 'primary';
}

/** "Upload" | "Screening" | "Application" for JobBatchOverviewItem.batch_type. */
export function batchTypeLabel(type: string): string {
  switch (type) {
    case 'SCREEN': return 'Screening';
    case 'APPLICATION': return 'Application';
    default: return 'Upload';
  }
}
