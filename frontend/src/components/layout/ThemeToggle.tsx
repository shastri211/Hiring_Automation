import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme, type Theme } from '../../hooks/useTheme';

const NEXT: Record<Theme, Theme> = { light: 'dark', dark: 'system', system: 'light' };
const ICON: Record<Theme, typeof Sun> = { light: Sun, dark: Moon, system: Monitor };
const LABEL: Record<Theme, string> = { light: 'Light theme', dark: 'Dark theme', system: 'System theme' };

export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();
  const Icon = ICON[theme];
  return (
    <button
      type="button"
      onClick={() => setTheme(NEXT[theme])}
      className="focus-ring rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)] transition-colors"
      aria-label={`Theme: ${LABEL[theme]}. Click to switch.`}
      title={LABEL[theme]}
    >
      <Icon size={18} />
    </button>
  );
};
