import { useRef, useState, type DragEvent, type KeyboardEvent, type ReactNode } from 'react';
import { Upload } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '../../utils/cn';
import { Button } from './Button';

/**
 * Dropzone — the one file-picking surface (resume upload, job-description
 * upload). Click, Enter/Space, or drop. Files are filtered to `accept`
 * (extensions, e.g. ['.pdf', '.docx']); anything else is skipped with a toast
 * saying so, rather than vanishing silently.
 */
interface DropzoneProps {
  accept: string[];
  multiple?: boolean;
  onFiles: (files: File[]) => void;
  title: ReactNode;
  hint?: ReactNode;
  browseLabel?: string;
  disabled?: boolean;
  className?: string;
}

export const Dropzone = ({ accept, multiple = false, onFiles, title, hint, browseLabel = 'Browse files', disabled, className }: DropzoneProps) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const allowed = accept.map((a) => a.toLowerCase());
  const label = accept.map((a) => a.replace('.', '').toUpperCase()).join(' or ');

  const handle = (incoming: File[]) => {
    const ok = incoming.filter((f) => allowed.some((ext) => f.name.toLowerCase().endsWith(ext)));
    const skipped = incoming.length - ok.length;
    if (skipped > 0) toast.error(`${skipped} file${skipped === 1 ? '' : 's'} skipped — only ${label} files are accepted.`);
    if (ok.length > 0) onFiles(multiple ? ok : ok.slice(0, 1));
  };

  const open = () => !disabled && inputRef.current?.click();

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!disabled) handle(Array.from(e.dataTransfer.files));
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      open();
    }
  };

  return (
    <div
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled || undefined}
      aria-label={typeof title === 'string' ? title : 'Choose files'}
      onClick={open}
      onKeyDown={onKeyDown}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'transition-base focus-ring flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-12 text-center',
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer',
        dragging
          ? 'border-[var(--border-focus)] bg-[var(--color-primary-subtle-bg)]'
          : 'border-[var(--border-input)] bg-[var(--bg-surface)] hover:border-[var(--border-focus)] hover:bg-[var(--bg-hover)]',
        className
      )}
    >
      <Upload size={22} aria-hidden="true" className="mb-3 text-[var(--text-tertiary)]" />
      <p className="text-card-title">{title}</p>
      {hint && <p className="text-body mt-1">{hint}</p>}
      <Button
        variant="secondary"
        size="sm"
        className="mt-4"
        disabled={disabled}
        onClick={(e) => { e.stopPropagation(); open(); }}
      >
        {browseLabel}
      </Button>
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        multiple={multiple}
        accept={accept.join(',')}
        tabIndex={-1}
        onChange={(e) => {
          if (e.target.files) handle(Array.from(e.target.files));
          e.target.value = ''; // allow re-selecting the same file
        }}
      />
    </div>
  );
};
