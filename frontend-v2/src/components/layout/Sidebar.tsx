import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Briefcase, Star, X,
  Users, Calendar, Database, Mail,
  FileText, Brain, MessageSquare, BarChart,
  Puzzle, Settings, ListChecks
} from 'lucide-react';
import clsx from 'clsx';

type NavItem = {
  to: string;
  label: string;
  icon: any;
  exact?: boolean;
  disabled?: boolean;
};

type NavGroup = {
  title: string;
  items: NavItem[];
};

export const Sidebar = ({ 
  isMobileOpen, 
  setMobileOpen 
}: { 
  isMobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
}) => {
  const navGroups: NavGroup[] = [
    {
      title: 'DASHBOARD',
      items: [
        { to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
      ]
    },
    {
      title: 'RECRUITING',
      items: [
        { to: '/jobs', label: 'Jobs', icon: Briefcase },
        { to: '/processing', label: 'Processing', icon: ListChecks },
        { to: '/candidates', label: 'Candidates', icon: Users },
        { to: '/shortlisted', label: 'Shortlisted', icon: Star },
        { to: '/interviews', label: 'Interviews', icon: Calendar },
        { to: '/talent-pool', label: 'Talent Pool', icon: Database },
      ]
    },
    {
      title: 'COMMUNICATION',
      items: [
        { to: '/outreach', label: 'Email / Outreach', icon: Mail },
        { to: '/templates', label: 'Templates', icon: FileText },
      ]
    },
    {
      title: 'INTELLIGENCE',
      items: [
        { to: '/ai-screening', label: 'AI Screening', icon: Brain },
        { to: '/interview-analysis', label: 'Interview Analysis', icon: MessageSquare },
        { to: '/analytics', label: 'Analytics', icon: BarChart },
      ]
    },
    {
      title: 'SYSTEM',
      items: [
        { to: '/integrations', label: 'Integrations', icon: Puzzle },
        { to: '/settings', label: 'Settings', icon: Settings },
      ]
    }
  ];

  return (
    <>
      {isMobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-30 cursor-default bg-slate-900/50 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={clsx(
        'w-64 bg-[var(--bg-surface)] border-r border-[var(--border-light)] flex flex-col z-40 transition-transform duration-300 md:relative md:translate-x-0 fixed inset-y-0 left-0',
        isMobileOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="h-16 flex items-center justify-between px-4 border-b border-[var(--border-light)]">
          <div className="flex items-center gap-2 font-bold text-lg text-[var(--color-primary-700)]">
            <Briefcase size={24} className="text-[var(--color-primary-600)]" />
            <span>RecruitPro</span>
          </div>
          <button className="md:hidden text-slate-500 hover:text-slate-700 focus-ring rounded" onClick={() => setMobileOpen(false)}>
            <X size={20} />
          </button>
        </div>
        <nav id="main-navigation" aria-label="Primary navigation" className="flex-1 p-4 flex flex-col gap-6 overflow-y-auto">
          {navGroups.map((group, i) => (
            <div key={i} className="flex flex-col gap-1">
              <h3 className="px-3 mb-1 text-xs font-semibold text-[var(--text-tertiary)] tracking-wider uppercase">
                {group.title}
              </h3>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.disabled ? '#' : item.to}
                  end={item.exact}
                  onClick={(e) => {
                    if (item.disabled) e.preventDefault();
                    else setMobileOpen(false);
                  }}
                  className={({ isActive }) => clsx(
                    'flex items-center gap-3 px-3 py-2.5 rounded-md font-medium transition-colors focus-ring',
                    item.disabled
                      ? 'text-[var(--text-tertiary)] cursor-not-allowed opacity-70'
                      : isActive
                        ? 'bg-[var(--color-primary-50)] text-[var(--color-primary-700)]'
                        : 'text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]'
                  )}
                  title={item.disabled ? "Coming Soon" : ""}
                >
                  <item.icon size={20} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
};
