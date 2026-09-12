import { useState } from 'react';
import { useEmailTemplates, useCreateTemplate } from '../hooks/useEmails';
import { Loader2, Plus, Mail, Pencil, Trash2 } from 'lucide-react';
import { Button } from '../components/ui/Button';

export const EmailTemplates = () => {
  const { data: templates, isLoading } = useEmailTemplates();
  const createMutation = useCreateTemplate();
  
  const [isCreating, setIsCreating] = useState(false);
  const [formData, setFormData] = useState({ name: '', subject: '', body_content: '' });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate(formData, {
      onSuccess: () => {
        setIsCreating(false);
        setFormData({ name: '', subject: '', body_content: '' });
      }
    });
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
            <Mail className="w-6 h-6 text-blue-600" /> Email Templates
          </h1>
          <p className="text-slate-500 text-sm mt-1">Manage reusable templates for candidate outreach.</p>
        </div>
        <Button onClick={() => setIsCreating(true)} className="flex items-center gap-2">
          <Plus className="w-4 h-4" /> New Template
        </Button>
      </div>

      {isCreating && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm mb-8">
          <h2 className="text-lg font-semibold text-slate-800 mb-4">Create Template</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Template Name</label>
              <input 
                required
                type="text" 
                value={formData.name}
                onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                className="w-full border-slate-300 rounded-md shadow-sm text-sm focus-ring"
                placeholder="e.g., Interview Invitation"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Subject</label>
              <input 
                required
                type="text" 
                value={formData.subject}
                onChange={e => setFormData(f => ({ ...f, subject: e.target.value }))}
                className="w-full border-slate-300 rounded-md shadow-sm text-sm focus-ring"
                placeholder="Invitation to interview for {{job_title}}"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Body Content</label>
              <p className="text-xs text-slate-500 mb-2">Available variables: {'{{candidate_name}}'}, {'{{job_title}}'}, {'{{interview_link}}'}</p>
              <textarea 
                required
                rows={6}
                value={formData.body_content}
                onChange={e => setFormData(f => ({ ...f, body_content: e.target.value }))}
                className="w-full border-slate-300 rounded-md shadow-sm text-sm focus-ring"
                placeholder="Hi {{candidate_name}}, we'd like to invite you..."
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="secondary" onClick={() => setIsCreating(false)}>Cancel</Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {createMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Template'}
              </Button>
            </div>
            {createMutation.isError && (
              <p className="text-red-500 text-sm mt-2">Failed to create template.</p>
            )}
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-blue-500" /></div>
      ) : templates && templates.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map(t => (
            <div key={t.id} className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 hover:shadow-md transition-shadow flex flex-col h-full">
              <div className="flex justify-between items-start mb-4">
                <h3 className="font-semibold text-slate-800 text-lg">{t.name}</h3>
                <div className="flex gap-2">
                  <button className="text-slate-400 hover:text-blue-600"><Pencil className="w-4 h-4" /></button>
                  <button className="text-slate-400 hover:text-red-600"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="text-sm font-medium text-slate-600 mb-2 truncate">Subj: {t.subject}</div>
              <div className="text-sm text-slate-500 bg-slate-50 p-3 rounded-lg border border-slate-100 flex-1 whitespace-pre-wrap overflow-hidden" style={{ display: '-webkit-box', WebkitLineClamp: 4, WebkitBoxOrient: 'vertical' }}>
                {t.body_content}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-20 bg-white rounded-xl border border-slate-200">
          <Mail className="w-12 h-12 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-800 mb-1">No templates yet</h3>
          <p className="text-slate-500">Create your first email template to speed up outreach.</p>
        </div>
      )}
    </div>
  );
};
