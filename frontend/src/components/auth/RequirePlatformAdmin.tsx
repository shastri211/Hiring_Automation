import type { ReactNode } from 'react';
import { ShieldAlert } from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';
import { EmptyState } from '../ui';

// Platform-level pages (shared provider configuration, e.g. Integrations)
// are only for platform operators - not for organization admins. The server
// enforces this too (403); this just avoids rendering a page that can't load.
export const RequirePlatformAdmin = ({ children }: { children: ReactNode }) => {
  const { isPlatformAdmin } = useAuth();
  if (!isPlatformAdmin) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <EmptyState
          icon={<ShieldAlert className="w-10 h-10 text-[var(--text-tertiary)]" />}
          title="Not available"
          description="This page manages platform-wide service configuration and is only available to platform administrators."
        />
      </div>
    );
  }
  return <>{children}</>;
};
