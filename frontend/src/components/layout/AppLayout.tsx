import { useEffect, useMemo, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { resolveLocation } from './navigation';
import { BreadcrumbContext } from '../../hooks/useBreadcrumbs';
import type { Crumb } from '../ui';

export const AppLayout = () => {
  const [isMobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { section, title } = resolveLocation(location.pathname);
  const [crumbs, setCrumbs] = useState<Crumb[] | null>(null);
  const crumbContext = useMemo(() => ({ setCrumbs }), []);

  // The header carries context only (section or breadcrumbs); the page body owns
  // the single visible title. The tab title still names the page.
  useEffect(() => {
    document.title = title ? `${title} · RecruitPro` : 'RecruitPro';
  }, [title]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
      <a
        href="#main-content"
        className="focus-ring sr-only z-50 rounded-md bg-[var(--bg-surface)] px-3 py-2 text-sm font-medium focus:not-sr-only focus:absolute focus:left-3 focus:top-3"
      >
        Skip to content
      </a>
      <Sidebar isMobileOpen={isMobileOpen} setMobileOpen={setMobileOpen} />
      <div className="flex h-screen min-w-0 flex-1 flex-col overflow-hidden">
        <Header section={section} crumbs={crumbs} onMenuClick={() => setMobileOpen(true)} isMenuOpen={isMobileOpen} />
        <main id="main-content" className="relative flex-1 overflow-y-auto p-4 md:p-8">
          <BreadcrumbContext.Provider value={crumbContext}>
            <Outlet />
          </BreadcrumbContext.Provider>
        </main>
      </div>
    </div>
  );
};
