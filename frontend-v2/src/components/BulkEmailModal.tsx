import { useState } from 'react';
import { useEmailTemplates, useBulkSendEmails } from '../hooks/useEmails';
import { Loader2, Mail, X } from 'lucide-react';
import { Button } from './ui/Button';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full overflow-hidden">
        <div className="flex justify-between items-center p-4 border-b border-slate-200">
          <h2 className="text-lg font-semibold text-slate-800 flex items-center gap-2">
            <Mail className="w-5 h-5 text-blue-600" />
            Send Email
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600"><X className="w-5 h-5" /></button>
        </div>
        
        <div className="p-6">
          <p className="text-slate-600 mb-4">
            You are about to send an email to <span className="font-bold">{selectedResumeIds.length} candidate(s)</span>.
          </p>
          
          <label className="block text-sm font-medium text-slate-700 mb-2">Select Template</label>
          {isLoading ? (
            <div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-blue-500" /></div>
          ) : (
            <select
              className="w-full border-slate-300 rounded-md shadow-sm text-sm focus-ring p-2 border"
              value={selectedTemplate || ''}
              onChange={(e) => setSelectedTemplate(Number(e.target.value))}
            >
              <option value="" disabled>-- Choose a template --</option>
              {templates?.map(t => (
                <option key={t.id} value={t.id}>{t.name} (Subject: {t.subject})</option>
              ))}
            </select>
          )}

          {bulkSendMutation.isError && (
            <div className="mt-4 p-3 bg-red-50 text-red-600 rounded-md text-sm">
              Failed to queue emails. Please try again or check the template.
            </div>
          )}
        </div>
        
        <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end gap-3">
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
      </div>
    </div>
  );
};
