import type { HTMLAttributes, InputHTMLAttributes } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '../../utils/cn';
import { Input } from './Primitives';

/**
 * FilterBar — the single toolbar row above a table: search on one side,
 * selects/toggles on the other. Wraps on narrow screens. Pair with `Tabs` for
 * status segments and `NativeSelect`/`Select` for the filters themselves.
 */
export const FilterBar = ({ className, ...props }: HTMLAttributes<HTMLDivElement>) => (
  <div className={cn('flex flex-wrap items-center gap-3', className)} {...props} />
);

export const FilterBarSpacer = () => <div className="hidden flex-1 sm:block" />;

interface SearchInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'onChange' | 'value'> {
  value: string;
  onValueChange: (value: string) => void;
  'aria-label': string;
}

export const SearchInput = ({ value, onValueChange, className, placeholder = 'Search…', ...props }: SearchInputProps) => (
  <div className={cn('relative w-full sm:w-64', className)}>
    <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" aria-hidden="true" />
    <Input
      type="search"
      value={value}
      onChange={(e) => onValueChange(e.target.value)}
      placeholder={placeholder}
      className="pl-9 pr-8 [&::-webkit-search-cancel-button]:hidden"
      {...props}
    />
    {value && (
      <button
        type="button"
        onClick={() => onValueChange('')}
        aria-label="Clear search"
        className="focus-ring absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
      >
        <X size={14} />
      </button>
    )}
  </div>
);
