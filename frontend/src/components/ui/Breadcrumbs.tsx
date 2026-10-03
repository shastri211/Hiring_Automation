import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface Crumb {
  label: string;
  /** Omit on the current (last) crumb. */
  to?: string;
}

/**
 * Single-line trail. Below `sm` only the current (last) crumb is shown so a
 * deep trail never wraps; the full trail returns from `sm` up.
 */
export const Breadcrumbs = ({ items, className }: { items: Crumb[]; className?: string }) => (
  <nav aria-label="Breadcrumb" className={cn('min-w-0', className)}>
    <ol className="flex min-w-0 flex-nowrap items-center gap-1.5 overflow-hidden text-sm">
      {items.map((item, i) => {
        const last = i === items.length - 1;
        const hiddenOnMobile = i < items.length - 1;
        return (
          <Fragment key={`${item.label}-${i}`}>
            <li className={cn('min-w-0', last || i === 0 ? 'max-w-[14rem] shrink-0' : 'max-w-[10rem] shrink truncate sm:max-w-[14rem]', hiddenOnMobile && 'hidden sm:block')}>
              {item.to && !last ? (
                <Link to={item.to} className="transition-base focus-ring rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                  {item.label}
                </Link>
              ) : (
                <span
                  aria-current={last ? 'page' : undefined}
                  className={cn('block truncate', last ? 'font-medium text-[var(--text-primary)]' : 'text-[var(--text-secondary)]')}
                >
                  {item.label}
                </span>
              )}
            </li>
            {!last && (
              <li aria-hidden="true" className={cn('shrink-0 text-[var(--text-tertiary)]', hiddenOnMobile && 'hidden sm:block')}>
                <ChevronRight size={14} />
              </li>
            )}
          </Fragment>
        );
      })}
    </ol>
  </nav>
);
