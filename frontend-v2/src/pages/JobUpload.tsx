import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, X, File as FileIcon, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { Button } from '../components/ui/Button';
import { toast } from 'sonner';

export const JobUpload = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [files, setFiles] = React.useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();

  const jobId = parseInt(id || '0', 10);

  const uploadMutation = useMutation({
    mutationFn: async (uploadFiles: File[]) => {
      const formData = new FormData();
      uploadFiles.forEach(f => formData.append('files', f));
      return jobsApi.uploadResumes(jobId, formData, (progressEvent) => {
        if (progressEvent.total) {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      });
    },
    onSuccess: (response) => {
      setFiles([]);
      queryClient.invalidateQueries({ queryKey: queryKeys.jobProgress(jobId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.candidates(jobId) });
      toast.success(`${response.accepted_files} resume${response.accepted_files === 1 ? '' : 's'} added to the processing queue.`);
    },
    onError: (error: { message?: string }) => {
      toast.error(error.message || 'Upload failed. Check the selected files and try again.');
    }
  });

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      f => f.name.toLowerCase().endsWith('.pdf') || f.name.toLowerCase().endsWith('.docx')
    );
    setFiles(prev => {
      const newFiles = [...prev];
      droppedFiles.forEach(df => {
        if (!newFiles.find(existing => existing.name === df.name && existing.size === df.size)) {
          newFiles.push(df);
        }
      });
      return newFiles;
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      setFiles(prev => {
        const newFiles = [...prev];
        selectedFiles.forEach(sf => {
          if (!newFiles.find(existing => existing.name === sf.name && existing.size === sf.size)) {
            newFiles.push(sf);
          }
        });
        return newFiles;
      });
    }
  };

  const removeFile = (index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleUpload = () => {
    if (files.length > 0) {
      setUploadProgress(0);
      uploadMutation.mutate(files);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-2 text-sm text-slate-500 mb-6">
        <button onClick={() => navigate('/jobs')} className="hover:text-slate-900 transition-colors">Jobs</button>
        <span>/</span>
        <button onClick={() => navigate(`/jobs/${id}`)} className="hover:text-slate-900 transition-colors">Job #{id}</button>
        <span>/</span>
        <span className="text-slate-900 font-medium">Upload Resumes</span>
      </div>

      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-slate-900 mb-1">Upload Resumes</h1>
        <p className="text-slate-500">Upload PDF or DOCX files for screening.</p>
      </div>

      <div
        className="border-2 border-dashed border-slate-200 rounded-xl p-12 mb-8 bg-slate-50 flex flex-col items-center justify-center text-center transition-colors hover:border-[var(--border-focus)] hover:bg-[var(--color-primary-50)] focus-ring"
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        style={{ cursor: 'pointer' }}
        tabIndex={0}
      >
        <div className="h-12 w-12 rounded-full bg-[var(--color-primary-100)] flex items-center justify-center mb-4">
          <Upload className="h-6 w-6 text-[var(--color-primary-600)]" />
        </div>
        <h3 className="text-lg font-medium text-slate-900 mb-1">Drop resumes here or click to browse</h3>
        <p className="text-sm text-slate-500 mb-4">Multiple files allowed • Accepted formats: PDF, DOCX</p>
        <Button variant="secondary" onClick={(e: any) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
          Browse Files
        </Button>
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          multiple
          accept=".pdf,.docx"
          onChange={handleFileSelect}
        />
      </div>

      {files.length > 0 && !uploadMutation.isSuccess && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden mb-6 shadow-sm">
          <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-slate-50/50">
            <h3 className="font-medium text-slate-900">{files.length} file{files.length !== 1 ? 's' : ''} selected</h3>
            <div className="flex gap-3">
              <Button variant="secondary" onClick={() => setFiles([])} disabled={uploadMutation.isPending}>
                Clear all
              </Button>
              <Button onClick={handleUpload} disabled={uploadMutation.isPending}>
                {uploadMutation.isPending ? (
                  <>
                    <Upload className="h-4 w-4 mr-2 animate-bounce" />
                    Uploading... {uploadProgress}%
                  </>
                ) : (
                  <>
                    <Upload className="h-4 w-4 mr-2" />
                    Upload
                  </>
                )}
              </Button>
            </div>
          </div>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="text-xs text-slate-500 bg-slate-50 uppercase sticky top-0">
                <tr>
                  <th className="px-6 py-3 font-medium">File</th>
                  <th className="px-6 py-3 font-medium">Size</th>
                  <th className="px-6 py-3 font-medium">Type</th>
                  <th className="px-6 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {files.map((file, i) => {
                  const isPdf = file.name.toLowerCase().endsWith('.pdf');
                  return (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-3">
                          {isPdf ? <FileText className="h-5 w-5 text-red-400" /> : <FileIcon className="h-5 w-5 text-blue-400" />}
                          <span className="font-medium text-slate-900 truncate max-w-xs">{file.name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-3 text-slate-500">{(file.size / 1024).toFixed(1)} KB</td>
                      <td className="px-6 py-3">
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-600">
                          {isPdf ? 'PDF' : 'DOCX'}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                          disabled={uploadMutation.isPending}
                          className="text-slate-400 hover:text-red-500 transition-colors disabled:opacity-50 p-1 focus-ring rounded"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {uploadMutation.isError && (
        <div className="mb-6 p-4 rounded-lg bg-red-50 border border-red-200 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
          <div>
            <h4 className="font-medium text-red-900">Upload failed</h4>
            <p className="text-sm text-red-700 mt-1">
              {uploadMutation.error instanceof Error ? uploadMutation.error.message : 'Please check file formats and try again.'}
            </p>
          </div>
        </div>
      )}

      {uploadMutation.isSuccess && uploadMutation.data && (
        <div className="mb-6 p-6 rounded-xl bg-emerald-50 border border-emerald-200">
          <div className="flex items-center gap-3 mb-4">
            <CheckCircle2 className="h-6 w-6 text-emerald-600" />
            <h4 className="font-medium text-emerald-900 text-lg">Upload Complete</h4>
          </div>
          
          <div className="flex gap-8 mb-6 text-sm">
            <div className="flex flex-col">
              <span className="text-emerald-800 font-semibold text-xl">{uploadMutation.data.accepted_files}</span>
              <span className="text-emerald-700">Accepted</span>
            </div>
            <div className="flex flex-col">
              <span className="text-amber-600 font-semibold text-xl">{uploadMutation.data.duplicate_files}</span>
              <span className="text-amber-700">Duplicates (Skipped)</span>
            </div>
            <div className="flex flex-col">
              <span className="text-red-600 font-semibold text-xl">{uploadMutation.data.invalid_files}</span>
              <span className="text-red-700">Invalid</span>
            </div>
          </div>
          
          <div className="flex gap-3">
            <Button onClick={() => navigate(`/jobs/${id}/processing`)}>
              View Processing
            </Button>
            <Button onClick={() => uploadMutation.reset()} variant="secondary">
              Upload More
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
