interface LoadingSpinnerProps {
  label?: string;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Spinner used inside a button while a request is in flight.
 *
 * The label is announced once, by the `role="status"` container. Earlier versions
 * also carried an sr-only copy and an `aria-live` child, so a screen reader heard
 * the same message three times per state change.
 */
export function LoadingSpinner({ label = 'Loading…', size = 'md' }: LoadingSpinnerProps) {
  const sizeMap = {
    sm: 'h-4 w-4 border-2',
    md: 'h-6 w-6 border-2',
    lg: 'h-10 w-10 border-4',
  };

  return (
    <span role="status" className="flex items-center gap-2">
      <span
        aria-hidden="true"
        className={[
          'animate-spin rounded-full border-gray-300 border-t-brand-600',
          sizeMap[size],
        ].join(' ')}
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
