import { getStatusDisplay } from '@/lib/statusUtils';
import type { NormalizedStatus } from '@/lib/types';

interface StatusBadgeProps {
  status: NormalizedStatus;
  /** Show the raw source string next to the normalized label. */
  rawLabel?: string;
  size?: 'sm' | 'md';
}

/**
 * Text-first badge for a normalized ticket status.
 *
 * Colour always accompanies text. `role="status"` was removed: it is a live-region
 * announcement, and a status label that never changes should not interrupt a screen
 * reader every time the list re-renders.
 */
export function StatusBadge({ status, rawLabel, size = 'md' }: StatusBadgeProps) {
  const display = getStatusDisplay(status);
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1';

  return (
    <span
      aria-label={`${display.ariaLabel}${rawLabel ? `, reported as ${rawLabel}` : ''}`}
      className={[
        'inline-flex items-center gap-1 rounded border font-medium',
        display.colorClass,
        display.textClass,
        display.borderClass,
        sizeClasses,
      ].join(' ')}
    >
      {display.label}
      {rawLabel && rawLabel !== display.shortLabel && (
        <span aria-hidden="true" className="ml-1 text-xs opacity-60">
          ({rawLabel})
        </span>
      )}
    </span>
  );
}
