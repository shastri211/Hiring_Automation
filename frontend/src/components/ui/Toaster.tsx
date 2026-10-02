import type { CSSProperties } from 'react';
import { Toaster as SonnerToaster } from 'sonner';
import { useTheme } from '../../hooks/useTheme';

/**
 * App toaster. Sonner's built-in "rich" colors are fixed light/dark palettes;
 * mapping its CSS variables onto our semantic tokens keeps toasts on-system in
 * both themes. Must render inside ThemeProvider.
 */
const toastVars = {
  '--normal-bg': 'var(--bg-surface)',
  '--normal-text': 'var(--text-primary)',
  '--normal-border': 'var(--border-strong)',
  '--success-bg': 'var(--color-success-subtle-bg)',
  '--success-text': 'var(--color-success-subtle-text)',
  '--success-border': 'var(--color-success-border)',
  '--error-bg': 'var(--color-danger-subtle-bg)',
  '--error-text': 'var(--color-danger-subtle-text)',
  '--error-border': 'var(--color-danger-border)',
  '--warning-bg': 'var(--color-warning-subtle-bg)',
  '--warning-text': 'var(--color-warning-subtle-text)',
  '--warning-border': 'var(--color-warning-border)',
  '--info-bg': 'var(--color-info-subtle-bg)',
  '--info-text': 'var(--color-info-subtle-text)',
  '--info-border': 'var(--color-info-border)',
  '--border-radius': 'var(--radius-lg)',
} as CSSProperties;

export const Toaster = () => {
  const { resolvedTheme } = useTheme();
  return <SonnerToaster position="top-right" richColors closeButton theme={resolvedTheme} style={toastVars} />;
};
