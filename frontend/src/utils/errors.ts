/**
 * The API client rejects with a plain ApiError object ({ message, status, ... }),
 * not an Error instance, so `error instanceof Error` is false for every failed
 * request. This reads the message from either shape.
 */
export function getErrorMessage(error: unknown, fallback?: string): string | undefined {
  if (error && typeof error === 'object' && 'message' in error && typeof (error as { message: unknown }).message === 'string') {
    return (error as { message: string }).message || fallback;
  }
  return fallback;
}
