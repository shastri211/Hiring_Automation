import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Upload, FileText } from 'lucide-react';
import { jobsApi } from '../api/jobs';
import { queryKeys } from '../api/queryKeys';
import { Button, Card, CardContent, CardFooter, Spinner, Input, Textarea, Label } from '../components/ui';
import { toast } from 'sonner';
import clsx from 'clsx';

export const JobWizard = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  
  const [title, setTitle] = useState('');
  const [mode, setMode] = useState<'manual' | 'upload'>('manual');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    }
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      toast.error('Job Title is required.');
      return;
    }
    mutation.mutate();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const droppedFile = Array.from(e.dataTransfer.files).find(
      f => f.name.toLowerCase().endsWith('.pdf') || f.name.toLowerCase().endsWith('.docx')
    );
    if (droppedFile) setFile(droppedFile);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  return (
    <div className="max-w-3xl mx-auto py-8">
      <h2 className="text-2xl font-semibold text-slate-900 mb-8 tracking-tight">Create New Job</h2>
      
      <Card>
        <form onSubmit={handleSubmit}>
          <CardContent className="p-8 flex flex-col gap-8">
            
            {/* Title Section */}
            <div>
              <Label className="mb-2 block text-base font-semibold">Job Title *</Label>
              <Input 
                value={title} 
                onChange={(e) => setTitle(e.target.value)} 
                placeholder="e.g. Senior Frontend Engineer" 
                disabled={mutation.isPending}
                required
              />
            </div>

            {/* Mode Toggle */}
            <div>
              <Label className="mb-3 block text-base font-semibold">Job Description Source *</Label>
              <div className="flex p-1 bg-slate-100 rounded-lg max-w-sm">
                <button
                  type="button"
                  className={clsx(
                    'flex-1 py-2 text-sm font-medium rounded-md transition-colors',
                    mode === 'manual' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-700'
                  )}
                  onClick={() => setMode('manual')}
                >
                  Manual Entry
                </button>
                <button
                  type="button"
                  className={clsx(
                    'flex-1 py-2 text-sm font-medium rounded-md transition-colors',
                    mode === 'upload' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-500 hover:text-slate-700'
                  )}
                  onClick={() => setMode('upload')}
                >
                  Upload File (PDF/DOCX)
                </button>
              </div>
            </div>

            {/* Description Section */}
            {mode === 'manual' ? (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <Label className="mb-2 block">Job Description</Label>
                <p className="text-sm text-slate-500 mb-3">Paste the full job description including responsibilities, requirements, and qualifications. Our AI will automatically structure this for you.</p>
                <Textarea 
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={12} 
                  placeholder="Enter the full job description here..." 
                  disabled={mutation.isPending}
                />
              </div>
            ) : (
              <div className="animate-in fade-in slide-in-from-bottom-2 duration-300">
                <Label className="mb-2 block">Upload Job Description</Label>
                <p className="text-sm text-slate-500 mb-3">Upload a PDF or DOCX file containing the job details. Our AI will automatically extract and structure the information.</p>
                
                {!file ? (
                  <div
                    className="border-2 border-dashed border-slate-200 rounded-xl p-12 bg-slate-50 flex flex-col items-center justify-center text-center transition-colors hover:border-[var(--border-focus)] hover:bg-[var(--color-primary-50)] focus-ring"
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    style={{ cursor: 'pointer' }}
                    tabIndex={0}
                  >
                    <div className="h-12 w-12 rounded-full bg-[var(--color-primary-100)] flex items-center justify-center mb-4">
                      <Upload className="h-6 w-6 text-[var(--color-primary-600)]" />
                    </div>
                    <h3 className="text-lg font-medium text-slate-900 mb-1">Drop JD file here or click to browse</h3>
                    <p className="text-sm text-slate-500 mb-4">Accepted formats: PDF, DOCX</p>
                    <Button type="button" variant="secondary" onClick={(e: any) => { e.stopPropagation(); fileInputRef.current?.click(); }}>
                      Browse Files
                    </Button>
                    <input
                      type="file"
                      ref={fileInputRef}
                      className="hidden"
                      accept=".pdf,.docx"
                      onChange={handleFileSelect}
                    />
                  </div>
                ) : (
                  <div className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between shadow-sm">
                    <div className="flex items-center gap-3">
                      <FileText className="h-8 w-8 text-blue-500" />
                      <div>
                        <p className="font-medium text-slate-900">{file.name}</p>
                        <p className="text-sm text-slate-500">{(file.size / 1024).toFixed(1)} KB</p>
                      </div>
                    </div>
                    <Button type="button" variant="secondary" size="sm" onClick={() => setFile(null)}>
                      Remove
                    </Button>
                  </div>
                )}
              </div>
            )}
          </CardContent>

          <CardFooter className="flex justify-between items-center bg-slate-50 p-6 border-t border-slate-100">
            <Button type="button" variant="secondary" onClick={() => navigate('/jobs')}>Cancel</Button>
            
            <Button type="submit" variant="primary" disabled={mutation.isPending || (mode === 'upload' && !file) || (mode === 'manual' && !description.trim())}>
              {mutation.isPending ? <><Spinner size={16} className="mr-2" /> Creating Job...</> : 'Create Job'}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
};
