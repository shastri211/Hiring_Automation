// Tiny standalone pub/sub for "the HR session just became unauthorized"
// events. Lives in its own module (rather than inside useAuth.tsx) so that
// client.ts can import it without creating a cycle: client.ts is imported by
// api/auth.ts, which useAuth.tsx imports, which would otherwise import back
// into client.ts's own module graph if this lived there.

type UnauthorizedHandler = () => void;

let handler: UnauthorizedHandler | null = null;

/** Registered by AuthProvider on mount; cleared on unmount. */
export const registerUnauthorizedHandler = (fn: UnauthorizedHandler | null) => {
  handler = fn;
};

/** Called by client.ts's response interceptor on a mid-session 401. */
export const notifyUnauthorized = () => {
  handler?.();
};
