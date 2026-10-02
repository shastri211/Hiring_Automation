import type { ReactNode } from 'react';

/**
 * Section — an eyebrow heading over a hairline rule, then content. The
 * editorial alternative to wrapping every block of a detail page in a Card:
 * sections are separated by whitespace and rules, not floating boxes.
 */
export const Section = ({
  title, icon, action, children, className, id,
}: {
  title: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) => (
  <section id={id} className={className}>
    <div className="mb-3 flex items-center justify-between gap-3 border-b border-[var(--border-light)] pb-2">
      <h3 className="text-eyebrow flex items-center gap-1.5">
        {icon && <span aria-hidden="true" className="text-[var(--text-tertiary)]">{icon}</span>}
        {title}
      </h3>
      {action}
    </div>
    {children}
  </section>
);
