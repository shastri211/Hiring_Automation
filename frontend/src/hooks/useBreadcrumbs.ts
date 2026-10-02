import { createContext, useContext, useEffect } from 'react';
import type { Crumb } from '../components/ui';

/**
 * Lets a page put its breadcrumb trail in the application header, so the
 * content area carries exactly one title. AppLayout provides the context and
 * renders the trail; pages without a trail fall back to the section label.
 */
export interface BreadcrumbContextValue {
  setCrumbs: (crumbs: Crumb[] | null) => void;
}

export const BreadcrumbContext = createContext<BreadcrumbContextValue | null>(null);

export function useBreadcrumbs(crumbs: Crumb[]) {
  const ctx = useContext(BreadcrumbContext);
  const setCrumbs = ctx?.setCrumbs;
  // A stable key: pages rebuild the array every render.
  const key = JSON.stringify(crumbs);

  useEffect(() => {
    setCrumbs?.(JSON.parse(key) as Crumb[]);
    return () => setCrumbs?.(null);
  }, [key, setCrumbs]);
}
