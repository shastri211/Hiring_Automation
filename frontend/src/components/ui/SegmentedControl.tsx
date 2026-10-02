import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '../../utils/cn';

/**
 * SegmentedControl — choose ONE option of a form field (e.g. "Manual entry" /
 * "Upload file"). Not for switching views of a page — that is `Tabs`.
 * A radio group: arrow keys move and select, one tab stop.
 */
interface SegmentedControlProps<T extends string> {
  options: { value: T; label: ReactNode }[];
  value: T;
  onChange: (value: T) => void;
  'aria-label': string;
  disabled?: boolean;
  className?: string;
}

export function SegmentedControl<T extends string>({ options, value, onChange, disabled, className, ...rest }: SegmentedControlProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent, index: number) => {
    const last = options.length - 1;
    let next: number | null = null;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = index === last ? 0 : index + 1;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = index === 0 ? last : index - 1;
    if (next === null) return;
    e.preventDefault();
    onChange(options[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="radiogroup"
      aria-label={rest['aria-label']}
      className={cn('inline-flex rounded-md border border-[var(--border-strong)] bg-[var(--bg-app)] p-0.5', className)}
    >
      {options.map((opt, i) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="radio"
            aria-checked={active}
            tabIndex={active ? 0 : -1}
            disabled={disabled}
            onClick={() => onChange(opt.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              'transition-base focus-ring rounded px-3.5 py-1.5 text-sm font-medium disabled:opacity-50',
              active
                ? 'border border-[var(--border-strong)] bg-[var(--bg-surface)] text-[var(--text-primary)]'
                : 'border border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
