import { Menu, LogOut, KeyRound, Plus } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Breadcrumbs, LinkButton, type Crumb } from '../ui';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '../../hooks/useAuth';
import { getInitials } from '../../utils/initials';

const iconButton =
  'focus-ring transition-base rounded-md p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]';

const UserMenu = () => {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <div className="ml-1 flex items-center gap-2 border-l border-[var(--border-light)] pl-3">
      <div
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary-subtle-bg)] text-[11px] font-semibold text-[var(--color-primary-subtle-text)]"
        title={user.email}
        aria-hidden="true"
      >
        {getInitials(user.name)}
      </div>
      <span className="hidden min-w-0 max-w-[12rem] flex-col leading-tight sm:flex">
        <span className="truncate text-sm font-medium text-[var(--text-primary)]">{user.name}</span>
        <span className="text-caption truncate" title={user.organization.name}>
          {user.organization.name}{user.role === 'admin' ? ' · Admin' : ''}
        </span>
      </span>
      <Link to="/change-password" className={iconButton} title="Change password" aria-label="Change password">
        <KeyRound size={16} />
      </Link>
      <button type="button" onClick={() => logout()} className={iconButton} title="Log out" aria-label="Log out">
        <LogOut size={16} />
      </button>
    </div>
  );
};

export const Header = ({
  section,
  crumbs,
  onMenuClick,
  isMenuOpen = false,
}: {
  section?: string;
  /** A page-provided trail; replaces the section label when present. */
  crumbs?: Crumb[] | null;
  onMenuClick: () => void;
  isMenuOpen?: boolean;
}) => {
  return (
    <header className="z-10 flex h-[var(--header-height)] shrink-0 items-center justify-between border-b border-[var(--border-light)] bg-[var(--bg-surface)] px-4 sm:px-6">
      <div className="flex min-w-0 items-center gap-3">
        <button
          type="button"
          className={`${iconButton} -ml-1.5 md:hidden`}
          onClick={onMenuClick}
          aria-label="Open navigation"
          aria-expanded={isMenuOpen}
          aria-controls="main-navigation"
        >
          <Menu size={20} />
        </button>
        {crumbs && crumbs.length > 0 ? (
          <Breadcrumbs items={crumbs} className="min-w-0" />
        ) : (
          section && <p className="text-eyebrow truncate">{section}</p>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        <ThemeToggle />
        <LinkButton to="/jobs/new" size="sm" className="max-sm:hidden">
          <Plus size={14} aria-hidden="true" /> New Job
        </LinkButton>
        <UserMenu />
      </div>
    </header>
  );
};
