interface ErrorBannerProps {
  message: string;
  code?: string | null;
  onDismiss?: () => void;
}

/**
 * Inline error banner for API/network errors.
 * Announces itself to assistive technology via role="alert".
 */
export function ErrorBanner({ message, code, onDismiss }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="rounded-lg border border-red-300 bg-red-50 p-4 flex items-start gap-3"
    >
      <span aria-hidden="true" className="text-red-500 text-xl mt-0.5">
        ✕
      </span>
      <div className="flex-1 space-y-1">
        <p className="font-semibold text-red-800 text-sm">Something went wrong</p>
        <p className="text-sm text-red-700">{message}</p>
        {code && (
          <p className="text-xs text-red-500 font-mono">Error code: {code}</p>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className="text-red-400 hover:text-red-600 focus:outline-none focus:ring-2 focus:ring-red-400 rounded"
        >
          <span aria-hidden="true">✕</span>
        </button>
      )}
    </div>
  );
}
