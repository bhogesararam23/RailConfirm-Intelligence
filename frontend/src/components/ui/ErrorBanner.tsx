interface ErrorBannerProps {
  message: string;
  code?: string | null;
  requestId?: string | null;
  onDismiss?: () => void;
}

/**
 * Inline banner for a failed request.
 *
 * `kind`-specific wording comes from the caller's message; the request id is shown
 * because it is the only way to tie what the user saw to a server-side log line, and
 * it carries no booking information.
 */
export function ErrorBanner({ message, code, requestId, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-lg border border-red-300 bg-red-50 p-4"
    >
      <span aria-hidden="true" className="mt-0.5 text-xl text-red-500">
        ✕
      </span>
      <div className="flex-1 space-y-1">
        <p className="text-sm font-semibold text-red-800">The request did not complete</p>
        <p className="text-sm text-red-700">{message}</p>
        {(code || requestId) && (
          <p className="text-xs text-red-600">
            {code && (
              <>
                Code: <span className="font-mono">{code}</span>
              </>
            )}
            {code && requestId && ' · '}
            {requestId && (
              <>
                Request id: <span className="font-mono">{requestId}</span>
              </>
            )}
          </p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss this error message"
          className="rounded text-red-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-400"
        >
          <span aria-hidden="true">✕</span>
        </button>
      )}
    </div>
  );
}
