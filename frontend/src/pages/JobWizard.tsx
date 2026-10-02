import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { FileText } from 'lucide-react';
import { toast } from 'sonner';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import { Button, Dropzone, Input, Label, PageHeader, SegmentedControl, Spinner, Textarea } from '../components/ui';

export const JobWizard = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  useBreadcrumbs([{ label: 'Jobs', to: '/jobs' }, { label: 'New job' }]);

  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<'manual' | 'upload'>('manual');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      formData.append('title', title);
      if (mode === 'manual') {
        if (!description.trim()) throw new Error('Job description is required.');
        formData.append('description', description);
      } else {
        if (!file) throw new Error('JD file is required.');
        formData.append('file', file);
      }
      return jobsApi.createJobFromUpload(formData);
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs() });
      toast.success('Job created successfully');
      navigate(`/jobs/${data.id}`);
    },
    onError: (error: any) => {
      toast.error(error?.message || 'Failed to create job');
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error('Job Title is required.');
      return;
    }
    mutation.mutate();
  };

  const busy = mutation.isPending;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        className="mb-8"
        title="Create new job"
        subtitle="Add a role. The description is structured by AI so candidates can be screened against it."
      />

      <form onSubmit={handleSubmit} className="flex flex-col gap-8">
        <div>
          <Label htmlFor="job-title" className="mb-2 block">Job title <span aria-hidden="true">*</span></Label>
          <Input
            id="job-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="e.g. Senior Frontend Engineer"
            disabled={busy}
            required
          />
        </div>

        <div>
          <p className="text-eyebrow mb-2">Job description source *</p>
          <SegmentedControl
            aria-label="Job description source"
            value={mode}
            onChange={setMode}
            disabled={busy}
            options={[
              { value: 'manual', label: 'Manual entry' },
              { value: 'upload', label: 'Upload file (PDF/DOCX)' },
            ]}
          />
        </div>

        {mode === 'manual' ? (
          <div>
            <Label htmlFor="job-description" className="mb-1.5 block">Job description</Label>
            <p className="text-body mb-3">Paste the full job description including responsibilities, requirements, and qualifications. Our AI will automatically structure this for you.</p>
            <Textarea
              id="job-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={12}
              placeholder="Enter the full job description here..."
              disabled={busy}
            />
          </div>
        ) : (
          <div>
            <p className="mb-1.5 text-sm font-medium text-[var(--text-secondary)]">Upload job description</p>
            <p className="text-body mb-3">Upload a PDF or DOCX file containing the job details. Our AI will automatically extract and structure the information.</p>
            {!file ? (
              <Dropzone
                accept={['.pdf', '.docx']}
                title="Drop JD file here or click to browse"
                hint="Accepted formats: PDF, DOCX"
                disabled={busy}
                onFiles={(files) => setFile(files[0])}
              />
            ) : (
              <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)] p-4">
                <div className="flex min-w-0 items-center gap-3">
                  <FileText size={20} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-[var(--text-primary)]">{file.name}</p>
                    <p className="text-caption tabular">{(file.size / 1024).toFixed(1)} KB</p>
                  </div>
                </div>
                <Button type="button" variant="secondary" size="sm" onClick={() => setFile(null)} disabled={busy}>
                  Remove
                </Button>
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-between border-t border-[var(--border-light)] pt-6">
          <Button type="button" variant="secondary" onClick={() => navigate('/jobs')} disabled={busy}>Cancel</Button>
          <Button
            type="submit"
            disabled={busy || (mode === 'upload' && !file) || (mode === 'manual' && !description.trim())}
          >
            {busy ? <><Spinner size={14} className="text-current" /> Creating job…</> : 'Create job'}
          </Button>
        </div>
      </form>
    </div>
  );
};
