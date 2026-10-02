import { useRef, type KeyboardEvent, type ReactNode } from 'react';
import { cn } from '../../utils/cn';

/**
 * Tabs — underline tabs that switch a *view* of the same page (a filter or
 * status segment), each with an optional count. Controlled; the caller owns
 * the value and renders the panel. Arrow keys move between tabs.
 */
export interface TabItem<T extends string> {
  value: T;
  label: ReactNode;
  count?: number | null;
  /** Tint the tab when active (e.g. a "Failed" segment). */
  tone?: 'default' | 'danger' | 'warning';
}

interface TabsProps<T extends string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  'aria-label': string;
  className?: string;
}

const ACTIVE_TONE = {
  default: 'border-[var(--text-primary)] text-[var(--text-primary)]',
  danger: 'border-[var(--color-danger-600)] text-[var(--color-danger-600)]',
  warning: 'border-[var(--color-warning-600)] text-[var(--color-warning-600)]',
};

export function Tabs<T extends string>({ tabs, value, onChange, className, ...rest }: TabsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End') return;
    e.preventDefault();
    const last = tabs.length - 1;
    const next =
      e.key === 'Home' ? 0
      : e.key === 'End' ? last
      : e.key === 'ArrowRight' ? (index === last ? 0 : index + 1)
      : index === 0 ? last : index - 1;
    onChange(tabs[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div
      role="tablist"
      aria-label={rest['aria-label']}
      className={cn('flex items-end gap-5 overflow-x-auto overflow-y-hidden border-b border-[var(--border-light)]', className)}
    >
      {tabs.map((tab, i) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="tab"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(tab.value)}
            onKeyDown={(e) => onKeyDown(e, i)}
            className={cn(
              'transition-base focus-ring -mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-0.5 pb-2.5 pt-1 text-sm font-medium',
              active ? ACTIVE_TONE[tab.tone ?? 'default'] : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            )}
          >
            {tab.label}
            {tab.count != null && <span className="tabular font-normal text-[var(--text-tertiary)]">({tab.count})</span>}
          </button>
        );
      })}
    </div>
  );
}
