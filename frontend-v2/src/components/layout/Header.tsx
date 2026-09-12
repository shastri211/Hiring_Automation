
import { Menu } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Button } from '../ui';
import { ThemeToggle } from './ThemeToggle';

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
      </div>
    </header>
  );
};
