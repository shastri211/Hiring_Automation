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
      return 'warning';
    case 'FAILED':
      return 'danger';
    case 'BLOCKED':
      return 'neutral';
    default:
      return 'neutral';
  }
}
