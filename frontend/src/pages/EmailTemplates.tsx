import { useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Mail, Pencil, Plus, Trash2 } from 'lucide-react';
import { useEmailTemplates, useCreateTemplate, useUpdateTemplate, useDeleteTemplate } from '../hooks/useEmails';
import { useConfirm } from '../hooks/useConfirm';
import {
  Alert, Badge, Button, DataTable, EmptyState, ErrorState, IconButton, Input, Label, PageHeader, Spinner, Textarea, type Column,
} from '../components/ui';
import { getErrorMessage } from '../utils/errors';
import type { EmailTemplate } from '../types';

const EMPTY_FORM = { name: '', subject: '', body_content: '' };
const VARIABLES = ['{{candidate_name}}', '{{job_title}}', '{{interview_link}}'];

export const EmailTemplates = () => {
  const { data: templates, isLoading, isError, error, refetch } = useEmailTemplates();
  const createMutation = useCreateTemplate();
  const updateMutation = useUpdateTemplate();
  const deleteMutation = useDeleteTemplate();
  const confirm = useConfirm();

  const [isCreating, setIsCreating] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [formData, setFormData] = useState(EMPTY_FORM);

  const resetFormAndClose = () => {
    setIsCreating(false);
    setEditingId(null);
    setFormData(EMPTY_FORM);
  };

  const startCreate = () => {
    setEditingId(null);
    setFormData(EMPTY_FORM);
    setIsCreating(true);
  };

  const startEdit = (template: EmailTemplate) => {
    setFormData({ name: template.name, subject: template.subject, body_content: template.body_content });
    setEditingId(template.id);
    setIsCreating(true);
  };

  const handleDelete = async (template: EmailTemplate) => {
    const ok = await confirm({
      title: 'Delete template?',
      description: `Delete "${template.name}"? Past sent emails keep their content but lose this template link. This cannot be undone.`,
      danger: true,
      confirmLabel: 'Delete',
    });
    if (ok) deleteMutation.mutate(template.id);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (editingId != null) {
      updateMutation.mutate({ id: editingId, patch: formData }, { onSuccess: resetFormAndClose });
    } else {
      createMutation.mutate(formData, { onSuccess: resetFormAndClose });
    }
  };

  const isSaving = createMutation.isPending || updateMutation.isPending;
  const isBusy = isSaving || deleteMutation.isPending;
  const saveError = getErrorMessage(createMutation.error) || getErrorMessage(updateMutation.error) || 'Failed to save template.';

  const columns: Column<EmailTemplate>[] = [
    {
      id: 'name',
      header: 'Template',
      mobile: 'title',
      className: 'w-[22%]',
      skeleton: 'text',
      cell: (t) => <span className="text-sm font-medium text-[var(--text-primary)]">{t.name}</span>,
    },
    {
      id: 'subject',
      header: 'Subject',
      className: 'w-[26%]',
      cell: (t) => <span className="line-clamp-2 text-sm text-[var(--text-secondary)]">{t.subject}</span>,
    },
    {
      id: 'body',
      header: 'Body',
      hideBelow: 'lg',
      mobile: 'body',
      cell: (t) => <p className="line-clamp-2 text-sm text-[var(--text-secondary)]">{t.body_content}</p>,
    },
    {
      id: 'updated',
      header: 'Updated',
      hideBelow: 'xl',
      mobile: 'hidden',
      className: 'w-32',
      cell: (t) => {
        const at = t.updated_at || t.created_at;
        return <span className="text-caption whitespace-nowrap">{at ? formatDistanceToNow(new Date(at), { addSuffix: true }) : '—'}</span>;
      },
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      mobile: 'actions',
      className: 'w-20',
      skeleton: 'actions',
      cell: (t) => (
        <div className="flex justify-end gap-0.5">
          <IconButton label={`Edit template ${t.name}`} icon={<Pencil size={15} />} disabled={isBusy} onClick={() => startEdit(t)} />
          <IconButton label={`Delete template ${t.name}`} tone="danger" icon={<Trash2 size={15} />} disabled={isBusy} onClick={() => handleDelete(t)} />
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        className="mb-6"
        title="Email templates"
        subtitle="Manage reusable templates for candidate outreach."
        actions={
          <Button onClick={startCreate} disabled={isCreating && editingId == null}>
            <Plus size={14} aria-hidden="true" /> New template
          </Button>
        }
      />

      {isCreating && (
        <section aria-label={editingId != null ? 'Edit template' : 'Create template'} className="mb-6 rounded-lg border border-[var(--border-strong)] bg-[var(--bg-surface)] p-5">
          <h2 className="text-section-heading mb-4">{editingId != null ? 'Edit template' : 'Create template'}</h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="tpl-name" className="mb-1.5 block">Template name</Label>
              <Input
                id="tpl-name"
                required
                autoFocus
                value={formData.name}
                onChange={(e) => setFormData((f) => ({ ...f, name: e.target.value }))}
                placeholder="e.g., Interview Invitation"
              />
            </div>
            <div>
              <Label htmlFor="tpl-subject" className="mb-1.5 block">Subject</Label>
              <Input
                id="tpl-subject"
                required
                value={formData.subject}
                onChange={(e) => setFormData((f) => ({ ...f, subject: e.target.value }))}
                placeholder="Invitation to interview for {{job_title}}"
              />
            </div>
            <div>
              <Label htmlFor="tpl-body" className="mb-1.5 block">Body</Label>
              <p className="text-caption mb-2 flex flex-wrap items-center gap-1.5">
                Available variables:
                {VARIABLES.map((v) => <Badge key={v} className="font-mono">{v}</Badge>)}
              </p>
              <Textarea
                id="tpl-body"
                required
                rows={7}
                value={formData.body_content}
                onChange={(e) => setFormData((f) => ({ ...f, body_content: e.target.value }))}
                placeholder="Hi {{candidate_name}}, we'd like to invite you..."
              />
            </div>
            {(createMutation.isError || updateMutation.isError) && <Alert variant="danger">{saveError}</Alert>}
            <div className="flex justify-end gap-2 border-t border-[var(--border-light)] pt-4">
              <Button type="button" variant="secondary" onClick={resetFormAndClose} disabled={isSaving}>Cancel</Button>
              <Button type="submit" disabled={isSaving}>
                {isSaving ? <><Spinner size={14} className="text-current" /> Saving…</> : 'Save template'}
              </Button>
            </div>
          </form>
        </section>
      )}

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load email templates" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : (
        <DataTable
          aria-label="Email templates"
          rows={templates ?? []}
          columns={columns}
          getRowId={(t) => t.id}
          isLoading={isLoading}
          skeletonRows={4}
          empty={
            <EmptyState
              icon={<Mail size={20} />}
              title="No templates yet"
              description="Create your first email template to speed up outreach."
              action={!isCreating ? <Button variant="secondary" onClick={startCreate}><Plus size={14} aria-hidden="true" /> New template</Button> : undefined}
            />
          }
        />
      )}
    </div>
  );
};
