import { useState } from 'react';
import { useEmailTemplates, useBulkSendEmails } from '../hooks/useEmails';
import { Loader2, Mail } from 'lucide-react';
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

export const BulkEmailModal = ({
  jobId,
  selectedResumeIds,
  onClose,
  onSuccess
}: {
  jobId: number;
  selectedResumeIds: number[];
  onClose: () => void;
  onSuccess: () => void;
}) => {
  const { data: templates, isLoading } = useEmailTemplates();
  const bulkSendMutation = useBulkSendEmails(jobId);
  const [selectedTemplate, setSelectedTemplate] = useState<number | null>(null);

  const handleSend = () => {
    if (!selectedTemplate) return;

    bulkSendMutation.mutate({
      resume_ids: selectedResumeIds,
      template_id: selectedTemplate
    }, {
      onSuccess: () => {
        onSuccess();
      }
    });
  };

  return (
    <Dialog open onOpenChange={(next) => { if (!next) onClose(); }}>
      <DialogContent className="max-w-lg">
        <DialogTitle className="flex items-center gap-2">
          <Mail className="w-5 h-5 text-[var(--color-primary-600)]" />
          Send Email
        </DialogTitle>
        <DialogDescription>
          You are about to send an email to <span className="font-bold text-slate-700">{selectedResumeIds.length} candidate(s)</span>.
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

          {bulkSendMutation.isError && (
            <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-md text-sm">
              Failed to queue emails. Please try again or check the template.
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 pt-2 border-t border-[var(--border-light)] mt-2">
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            onClick={handleSend}
            disabled={!selectedTemplate || bulkSendMutation.isPending}
            className="flex items-center gap-2"
          >
            {bulkSendMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
            Send {selectedResumeIds.length} Emails
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
