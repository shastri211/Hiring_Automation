import { NavLink } from 'react-router-dom';
import { X } from 'lucide-react';
import clsx from 'clsx';
import { useMatchSuggestions } from '../../hooks/useCandidateIdentity';
import { useAuth } from '../../hooks/useAuth';
import { NAV_GROUPS } from './navigation';

export const Sidebar = ({
  isMobileOpen,
  setMobileOpen,
}: {
  isMobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}) => {
  // Small, review-queue-sized list (auto-filed off a phone-exact match) - a
  // plain list fetch doubles as the pending count, so no dedicated count
  // endpoint is needed. Shares its query cache with the Duplicate Candidates
  // page itself (same query key), so this doesn't add an extra request
  // beyond what that page already needs.
  const { data: pendingSuggestions } = useMatchSuggestions('PENDING');
  const pendingCount = pendingSuggestions?.length ?? 0;
  const { user, isPlatformAdmin } = useAuth();

  const badgeFor = (to: string) => (to === '/candidates/duplicates' ? pendingCount : 0);

  return (
    <>
      {isMobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 cursor-default bg-[var(--bg-overlay)] md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex w-[var(--sidebar-width)] flex-col border-r border-[var(--border-light)] bg-[var(--bg-surface)] transition-transform duration-200 md:relative md:translate-x-0',
          isMobileOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-[var(--header-height)] shrink-0 items-center justify-between border-b border-[var(--border-light)] px-4">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-6 w-6 items-center justify-center rounded bg-[var(--accent)] text-[13px] font-bold text-[var(--accent-fg)]"
            >
              R
            </span>
            <span className="text-[15px] font-semibold tracking-tight text-[var(--text-primary)]">RecruitPro</span>
          </div>
          <button
            type="button"
            className="focus-ring rounded p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        {user?.organization && (
          <div className="border-b border-[var(--border-light)] px-4 py-3" title="Your organization">
            <p className="text-eyebrow">Organization</p>
            <p className="mt-0.5 truncate text-sm font-medium text-[var(--text-primary)]">{user.organization.name}</p>
          </div>
        )}

        <nav id="main-navigation" aria-label="Primary navigation" className="flex flex-1 flex-col gap-5 overflow-y-auto px-3 py-4">
          {NAV_GROUPS.map((group) => {
            const items = group.items.filter((item) => !item.platformAdminOnly || isPlatformAdmin);
            if (items.length === 0) return null;
            return (
              <div key={group.title} className="flex flex-col gap-0.5">
                <h3 className="text-eyebrow mb-1 px-2">{group.title}</h3>
                {items.map((item) => {
                  const badge = badgeFor(item.to);
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      end={item.exact}
                      onClick={() => setMobileOpen(false)}
                      className={({ isActive }) =>
                        clsx(
                          'focus-ring transition-base flex h-8 items-center gap-2.5 rounded-md px-2 text-sm',
                          isActive
                            ? 'bg-[var(--bg-hover)] font-medium text-[var(--text-primary)]'
                            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                        )
                      }
                    >
                      {({ isActive }) => (
                        <>
                          <item.icon
                            size={16}
                            aria-hidden="true"
                            className={isActive ? 'text-[var(--color-primary-600)]' : 'text-[var(--text-tertiary)]'}
                          />
                          <span className="flex-1 truncate">{item.label}</span>
                          {badge > 0 && (
                            <span
                              className="tabular min-w-[1.25rem] rounded-full bg-[var(--accent)] px-1.5 py-px text-center text-[11px] font-semibold text-[var(--accent-fg)]"
                              aria-label={`${badge} pending`}
                            >
                              {badge}
                            </span>
                          )}
                        </>
                      )}
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </nav>
      </aside>
    </>
  );
};
