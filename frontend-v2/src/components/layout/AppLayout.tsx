import { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

export const AppLayout = () => {
  const [isMobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();

  const getPageTitle = () => {
    if (location.pathname === '/') return 'Dashboard';
    if (location.pathname.startsWith('/jobs')) return 'Jobs';
    if (location.pathname.startsWith('/candidates')) return 'All Candidates';
    if (location.pathname.startsWith('/shortlisted')) return 'Shortlisted Candidates';
    if (location.pathname.startsWith('/interviews')) return 'All Interviews';
    if (location.pathname.startsWith('/interview/')) return 'Interview Workspace';
    if (location.pathname.startsWith('/talent-pool')) return 'Talent Pool';
    if (location.pathname.startsWith('/outreach')) return 'Email & Outreach';
    if (location.pathname.startsWith('/templates')) return 'Message Templates';
    if (location.pathname.startsWith('/ai-screening')) return 'AI Screening';
    if (location.pathname.startsWith('/interview-analysis')) return 'Interview Analysis';
    if (location.pathname.startsWith('/analytics')) return 'Analytics';
    if (location.pathname.startsWith('/integrations')) return 'Integrations';
    if (location.pathname.startsWith('/settings')) return 'Settings';
    return '';
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
      <Sidebar isMobileOpen={isMobileOpen} setMobileOpen={setMobileOpen} />
      <div className="flex flex-1 flex-col min-w-0 h-screen overflow-hidden">
        <Header title={getPageTitle()} onMenuClick={() => setMobileOpen(true)} isMenuOpen={isMobileOpen} />
        <main className="flex-1 overflow-y-auto p-4 md:p-8 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
