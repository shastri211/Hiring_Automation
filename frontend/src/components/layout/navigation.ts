import {
  LayoutDashboard, Briefcase, Star, Users, Calendar, Database, Mail,
  FileText, Brain, MessageSquare, BarChart, Puzzle, Settings, ListChecks, Users2,
  type LucideIcon,
} from 'lucide-react';

/**
 * Single source of truth for primary navigation. The Sidebar renders it, and
 * the Header derives its section/page label from it, so the two can't drift.
 * Routes themselves live in routes/index.tsx — this only describes the chrome.
 */
export interface NavItem {
  to: string;
  /** Sidebar label. */
  label: string;
  /** Page title shown in the header (defaults to `label`). */
  title?: string;
  icon: LucideIcon;
  /** Match the path exactly (otherwise it also matches nested routes). */
  exact?: boolean;
  /** Only shown to platform admins. */
  platformAdminOnly?: boolean;
}

export interface NavGroup {
  title: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    title: 'Dashboard',
    items: [{ to: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true }],
  },
  {
    title: 'Recruiting',
    items: [
      { to: '/jobs', label: 'Jobs', icon: Briefcase },
      { to: '/processing', label: 'Processing', icon: ListChecks },
      { to: '/candidates', label: 'Candidates', title: 'All Candidates', icon: Users },
      { to: '/candidates/duplicates', label: 'Duplicate Candidates', icon: Users2 },
      { to: '/shortlisted', label: 'Shortlisted', title: 'Shortlisted Candidates', icon: Star },
      { to: '/interviews', label: 'Interviews', title: 'All Interviews', icon: Calendar },
      { to: '/talent-pool', label: 'Talent Pool', icon: Database },
    ],
  },
  {
    title: 'Communication',
    items: [
      { to: '/outreach', label: 'Email / Outreach', title: 'Email & Outreach', icon: Mail },
      { to: '/templates', label: 'Templates', title: 'Message Templates', icon: FileText },
    ],
  },
  {
    title: 'Intelligence',
    items: [
      { to: '/ai-screening', label: 'AI Screening', icon: Brain },
      { to: '/interview-analysis', label: 'Interview Analysis', icon: MessageSquare },
      { to: '/analytics', label: 'Analytics', icon: BarChart },
    ],
  },
  {
    title: 'System',
    items: [
      // Platform-level (shared provider config) - platform admins only.
      { to: '/integrations', label: 'Integrations', icon: Puzzle, platformAdminOnly: true },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

// Routes that live under the app shell but aren't sidebar entries.
const EXTRA_LOCATIONS: { prefix: string; section: string; title: string }[] = [
  { prefix: '/interview/', section: 'Recruiting', title: 'Interview Workspace' },
];

/** Section + page title for the header, by longest matching path prefix. */
export function resolveLocation(pathname: string): { section?: string; title: string } {
  let best: { section: string; title: string; len: number } | null = null;
  for (const group of NAV_GROUPS) {
    for (const item of group.items) {
      const matches = item.exact ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`);
      if (matches && (!best || item.to.length > best.len)) {
        best = { section: group.title, title: item.title ?? item.label, len: item.to.length };
      }
    }
  }
  for (const extra of EXTRA_LOCATIONS) {
    if (pathname.startsWith(extra.prefix)) return { section: extra.section, title: extra.title };
  }
  return best ? { section: best.section, title: best.title } : { title: '' };
}
