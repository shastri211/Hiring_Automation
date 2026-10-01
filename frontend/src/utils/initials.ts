export const getInitials = (name?: string | null): string => {
  if (!name) return '?';
  const initials = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('');
  return initials || '?';
};
