interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Accessible loading spinner with an ARIA live region announcement.
 */
export function LoadingSpinner({
  label = 'Loading…',
  size = 'md',
}: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-10 w-10 border-4',
  };

  return (
    <div
      role="status"
      aria-label={label}
      className="flex items-center gap-2"
    >
      <div
        aria-hidden="true"
        className={[
          'animate-spin rounded-full border-gray-300 border-t-brand-600',
          sizeMap[size],
        ].join(' ')}
      />
      <span className="sr-only">{label}</span>
      <span className="text-sm text-gray-600" aria-live="polite">
        {label}
      </span>
    </div>
  );
}
