import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Loader2, Mail, AlertTriangle } from 'lucide-react';
import { useEmailTemplates, emailQueryKeys } from '../hooks/useEmails';
import { emailsApi } from '../api/emails';
import {
  Button,
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
  Label,
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from './ui';

export type ResumeGroup = {
  jobId: number;
  resumeIds: number[];
  // Optional, for friendlier failure messages when sending across jobs
  // (Global Candidates / Shortlisted). JobCandidates' single-job usage
  // doesn't need it - falls back to "Job #<id>".
  jobTitle?: string;
};

// A group only counts as fully "succeeded" when the backend actually queued
// every requested resume - a 200 response with queued_count 0 (every
// candidate skipped: no email on file, no live interview link if the
// template needs one, or already sent) used to be treated as success with
// no indication anything was wrong. "failed" now covers both a real HTTP
// error and a queued_count short of what was requested.
type GroupOutcome = { group: ResumeGroup; queued: number; requestError: boolean };
type SendOutcome = { succeeded: ResumeGroup[]; failed: GroupOutcome[] };

const groupLabel = (group: ResumeGroup) => group.jobTitle || `Job #${group.jobId}`;

export const BulkEmailModal = ({
  resumeGroups,
  onClose,
  onSuccess,
}: {
  resumeGroups: ResumeGroup[];
  onClose: () => void;
  onSuccess: () => void;
}) => {
  const { data: templates, isLoading } = useEmailTemplates();
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);
  // Starts as every group; narrows to just the failed ones after a partial
  // failure, so "Retry" only re-attempts what didn't go through.
  const [pendingGroups, setPendingGroups] = useState<ResumeGroup[]>(resumeGroups);
  const [lastOutcome, setLastOutcome] = useState<SendOutcome | null>(null);
  const queryClient = useQueryClient();

  const totalResumes = resumeGroups.reduce((sum, g) => sum + g.resumeIds.length, 0);

  const sendMutation = useMutation({
    mutationFn: async ({ groups, templateId }: { groups: ResumeGroup[]; templateId: number }): Promise<SendOutcome> => {
      // One bulk-send call per job group - the backend endpoint is
      // job-scoped - settled independently so one job's failure never
      // blocks the others from sending.
      const settled = await Promise.allSettled(
        groups.map((group) =>
          emailsApi.bulkSend(group.jobId, {
            resume_ids: group.resumeIds,
            template_id: templateId,
          })
        )
      );
      const succeeded: ResumeGroup[] = [];
      const failed: GroupOutcome[] = [];
      settled.forEach((result, i) => {
        const group = groups[i];
        if (result.status === 'fulfilled' && result.value.queued_count === group.resumeIds.length) {
          succeeded.push(group);
        } else {
          failed.push({
            group,
            queued: result.status === 'fulfilled' ? result.value.queued_count : 0,
            requestError: result.status === 'rejected',
          });
        }
      });
      return { succeeded, failed };
    },
    onSuccess: ({ succeeded, failed }) => {
      succeeded.forEach((group) => {
        group.resumeIds.forEach((resumeId) => {
          queryClient.invalidateQueries({ queryKey: emailQueryKeys.candidateHistory(resumeId) });
        });
      });
      failed.forEach(({ group, queued }) => {
        if (queued > 0) {
          group.resumeIds.forEach((resumeId) => {
            queryClient.invalidateQueries({ queryKey: emailQueryKeys.candidateHistory(resumeId) });
          });
        }
      });
      setLastOutcome({ succeeded, failed });
      setPendingGroups(failed.map((f) => f.group));
      if (failed.length === 0) {
        onSuccess();
      }
    },
  });

  const handleSend = () => {
    if (!selectedTemplate || pendingGroups.length === 0) return;
    sendMutation.mutate({ groups: pendingGroups, templateId: selectedTemplate });
  };

  const hasPartialFailure = !!lastOutcome && lastOutcome.failed.length > 0;
  const pendingCount = pendingGroups.reduce((sum, g) => sum + g.resumeIds.length, 0);
  // Both counts describe only the most recent attempt (a retry re-submits
  // whatever's still in pendingGroups, which can itself queue only some of
  // its candidates) - reporting "queued X of Y this attempt" stays accurate
  // across any number of retries, unlike trying to accumulate a running
  // total across attempts.
  const attemptedThisAttempt = lastOutcome
    ? [...lastOutcome.succeeded, ...lastOutcome.failed.map((f) => f.group)]
        .reduce((sum, g) => sum + g.resumeIds.length, 0)
    : totalResumes;
  const queuedThisAttempt = lastOutcome
    ? lastOutcome.succeeded.reduce((sum, g) => sum + g.resumeIds.length, 0)
      + lastOutcome.failed.reduce((sum, f) => sum + f.queued, 0)
    : 0;

  return (
    <Dialog open onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="flex items-center gap-2">
          <Mail className="w-5 h-5 text-[var(--color-primary-600)]" />
          Send Email
        </DialogTitle>
        <DialogDescription>
          You are about to send an email to <span className="font-bold text-slate-700">{totalResumes} candidate(s)</span>
          {resumeGroups.length > 1 ? ` across ${resumeGroups.length} jobs` : ''}.
        </DialogDescription>

        <div>
          <Label className="block mb-2">Select Template</Label>
          {isLoading ? (
            <div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-[var(--color-primary-500)]" /></div>
          ) : (
            <Select
              value={selectedTemplate ? String(selectedTemplate) : undefined}
              onValueChange={(value) => setSelectedTemplate(Number(value))}
            >
              <SelectTrigger>
                <SelectValue placeholder="-- Choose a template --" />
              </SelectTrigger>
              <SelectContent>
                {templates?.map(t => (
                  <SelectItem key={t.id} value={String(t.id)}>{t.name} (Subject: {t.subject})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}

          <p className="mt-4 text-xs text-[var(--text-tertiary)]">
            Sent to each candidate's own email address, as extracted from their resume - there is no test
            recipient or redirect.
          </p>

          {sendMutation.isError && (
            <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-md text-sm">
              Failed to queue emails. Please try again or check the template.
            </div>
          )}

          {hasPartialFailure && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-200 text-amber-800 rounded-md text-sm space-y-2">
              <div className="flex items-center gap-2 font-medium">
                <AlertTriangle className="w-4 h-4" />
                Queued {queuedThisAttempt} of {attemptedThisAttempt} in this attempt
              </div>
              <div>
                Not fully queued for these job(s):
                <ul className="list-disc list-inside mt-1">
                  {lastOutcome!.failed.map(({ group, queued, requestError }) => (
                    <li key={group.jobId}>
                      {groupLabel(group)} - {requestError
                        ? 'request failed'
                        : `${queued} of ${group.resumeIds.length} queued (others skipped: no email on file, no live interview link if the template needs one, or already sent)`}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border-light)] mt-2">
          <Button variant="secondary" onClick={onClose}>
            {hasPartialFailure ? 'Close' : 'Cancel'}
          </Button>
          <Button
            onClick={handleSend}
            disabled={!selectedTemplate || sendMutation.isPending || pendingGroups.length === 0}
            className="flex items-center gap-2"
          >
            {sendMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
            {hasPartialFailure ? `Retry ${pendingCount} Not Fully Queued` : `Send ${totalResumes} Emails`}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
