import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Upload, X } from 'lucide-react';
import { toast } from 'sonner';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { getErrorMessage } from '../utils/errors';
import { useBreadcrumbs } from '../hooks/useBreadcrumbs';
import {
  Alert, Badge, Button, DataTable, Dropzone, IconButton, PageHeader, Progress, Section, StatTile, type Column,
} from '../components/ui';

const sameFile = (a: File, b: File) => a.name === b.name && a.size === b.size;
const isPdf = (f: File) => f.name.toLowerCase().endsWith('.pdf');

export const JobUpload = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [files, setFiles] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const queryClient = useQueryClient();

  const jobId = parseInt(id || '0', 10);

  const { data: job } = useQuery({
    queryKey: queryKeys.job(jobId),
    queryFn: () => jobsApi.getJob(jobId),
    enabled: jobId > 0,
  });
  useBreadcrumbs([{ label: 'Jobs', to: '/jobs' }, { label: job?.title || 'Job', to: `/jobs/${id}` }, { label: 'Upload resumes' }]);

  const uploadMutation = useMutation({
    mutationFn: async (uploadFiles: File[]) => {
      const formData = new FormData();
      uploadFiles.forEach((f) => formData.append('files', f));
      return jobsApi.uploadResumes(jobId, formData, (progressEvent) => {
        if (progressEvent.total) {
          setUploadProgress(Math.round((progressEvent.loaded * 100) / progressEvent.total));
        }
      });
    },
    onSuccess: (response) => {
      setFiles([]);
      queryClient.invalidateQueries({ queryKey: queryKeys.jobProgress(jobId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      // The cross-job Processing page reads a separate query key - without
      // this, the new UPLOAD batch is invisible there until its 5-minute
      // staleTime lapses.
      queryClient.invalidateQueries({ queryKey: queryKeys.batchesOverview() });
      toast.success(`${response.accepted_files} resume${response.accepted_files === 1 ? '' : 's'} added to the processing queue.`);
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Upload failed. Check the selected files and try again.');
    },
  });

  const addFiles = (incoming: File[]) =>
    setFiles((prev) => [...prev, ...incoming.filter((f) => !prev.some((existing) => sameFile(existing, f)))]);

  const handleUpload = () => {
    if (files.length > 0) {
      setUploadProgress(0);
      uploadMutation.mutate(files);
    }
  };

  const uploading = uploadMutation.isPending;
  const result = uploadMutation.isSuccess ? uploadMutation.data : null;

  const removeButton = (f: File) => (
    <IconButton
      label={`Remove ${f.name}`}
      tone="danger"
      icon={<X size={15} />}
      disabled={uploading}
      onClick={() => setFiles((prev) => prev.filter((x) => !sameFile(x, f)))}
    />
  );

  const columns: Column<File>[] = [
    {
      id: 'file',
      header: 'File',
      mobile: 'title',
      cell: (f) => (
        <div className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2.5">
            <FileText size={16} aria-hidden="true" className="shrink-0 text-[var(--text-tertiary)]" />
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium text-[var(--text-primary)]">{f.name}</span>
              {/* Size and type live under the name on mobile; separate columns from md up. */}
              <span className="text-caption tabular md:hidden">{(f.size / 1024).toFixed(1)} KB · {isPdf(f) ? 'PDF' : 'DOCX'}</span>
            </span>
          </span>
          <span className="md:hidden">{removeButton(f)}</span>
        </div>
      ),
    },
    {
      id: 'size',
      header: 'Size',
      align: 'right',
      mobile: 'hidden',
      className: 'w-28',
      cell: (f) => <span className="tabular text-sm text-[var(--text-secondary)]">{(f.size / 1024).toFixed(1)} KB</span>,
    },
    { id: 'type', header: 'Type', mobile: 'hidden', className: 'w-24', cell: (f) => <Badge>{isPdf(f) ? 'PDF' : 'DOCX'}</Badge> },
    {
      id: 'remove',
      header: <span className="sr-only">Remove</span>,
      align: 'right',
      mobile: 'hidden',
      className: 'w-14',
      cell: (f) => removeButton(f),
    },
  ];

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader className="mb-6" title="Upload resumes" subtitle="Upload PDF or DOCX files for screening." />

      {!result && (
        <Dropzone
          multiple
          accept={['.pdf', '.docx']}
          title="Drop resumes here or click to browse"
          hint="Multiple files allowed · PDF and DOCX"
          browseLabel="Browse files"
          disabled={uploading}
          onFiles={addFiles}
          className="mb-6"
        />
      )}

      {files.length > 0 && !result && (
        <section aria-label="Selected files" className="mb-6">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-card-title tabular">{files.length} file{files.length === 1 ? '' : 's'} selected</h2>
            <div className="flex gap-2">
              <Button variant="secondary" onClick={() => setFiles([])} disabled={uploading}>Clear all</Button>
              <Button onClick={handleUpload} disabled={uploading}>
                <Upload size={14} aria-hidden="true" className={uploading ? 'animate-bounce' : undefined} />
                {uploading ? `Uploading… ${uploadProgress}%` : 'Upload'}
              </Button>
            </div>
          </div>
          {uploading && (
            <Progress className="mb-3" value={uploadProgress} aria-label="Upload progress" />
          )}
          <DataTable
            aria-label="Files to upload"
            rows={files}
            columns={columns}
            getRowId={(f) => `${f.name}:${f.size}`}
            className="max-h-96 overflow-auto"
          />
        </section>
      )}

      {uploadMutation.isError && (
        <Alert variant="danger" className="mb-6" title="Upload failed">
          {getErrorMessage(uploadMutation.error, 'Please check file formats and try again.')}
        </Alert>
      )}

      {result && (
        <Section title="Upload complete" className="mb-6">
          <Alert variant="success" className="mb-5">
            Your resumes are in the processing queue. Extraction and profiling run in the background.
          </Alert>
          <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="Accepted" value={result.accepted_files} />
            <StatTile label="Duplicates skipped" value={result.duplicate_files} />
            <StatTile label="Invalid" value={result.invalid_files} tone={result.invalid_files > 0 ? 'danger' : 'default'} />
            {result.failed_files > 0 && <StatTile label="Failed (corrupt)" value={result.failed_files} tone="danger" />}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => navigate(`/jobs/${id}/processing`)}>View processing</Button>
            <Button variant="secondary" onClick={() => uploadMutation.reset()}>Upload more</Button>
          </div>
        </Section>
      )}
    </div>
  );
};
