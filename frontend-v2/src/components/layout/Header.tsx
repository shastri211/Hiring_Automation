
import { Menu, LogOut } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui';
import { ThemeToggle } from './ThemeToggle';
import { useAuth } from '../../hooks/useAuth';

const getInitials = (name: string) =>
  name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?';

const UserMenu = () => {
  const { user, logout } = useAuth();
  if (!user) return null;

  return (
    <div className="flex items-center gap-2 pl-2 ml-1 border-l border-[var(--border-light)]">
      <div
        className="w-8 h-8 rounded-full bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] flex items-center justify-center text-xs font-semibold shrink-0"
        title={user.email}
      >
        {getInitials(user.name)}
      </div>
      <span className="hidden sm:inline text-sm font-medium text-[var(--text-primary)] max-w-[10rem] truncate">
        {user.name}
      </span>
      <button
        onClick={() => logout()}
        className="focus-ring rounded p-1.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors"
        title="Log out"
        aria-label="Log out"
      >
        <LogOut size={16} />
      </button>
    </div>
  );
};

export const Header = ({
  title,
  onMenuClick,
  isMenuOpen = false,
}: {
  title?: string;
  onMenuClick: () => void;
  isMenuOpen?: boolean;
}) => {
  return (
    <header className="h-16 bg-[var(--bg-surface)] border-b border-[var(--border-light)] flex items-center justify-between px-4 sm:px-6 shrink-0 shadow-sm z-10">
      <div className="flex items-center gap-4">
        <button
          className="focus-ring -ml-1 rounded p-1 text-slate-500 hover:text-slate-700 md:hidden"
          onClick={onMenuClick}
          aria-label="Open navigation"
          aria-expanded={isMenuOpen}
          aria-controls="main-navigation"
        >
          <Menu size={24} />
        </button>
        {title && <h1 className="text-xl font-semibold text-[var(--text-primary)] tracking-tight">{title}</h1>}
      </div>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Link to="/jobs/new" className="focus-ring rounded-md inline-block">
          <Button variant="primary" size="sm" tabIndex={-1}>
            + New Job
          </Button>
        </Link>
        <UserMenu />
      </div>
    </header>
  );
};
