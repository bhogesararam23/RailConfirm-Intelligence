import { getStatusDisplay } from '@/lib/statusUtils';
import type { NormalizedStatus } from '@/lib/types';

interface StatusBadgeProps {
  status: NormalizedStatus;
  /** Override the label text (e.g. to show raw status alongside normalized) */
  rawLabel?: string;
  size?: 'sm' | 'md';
}

/**
 * Color-coded badge for normalized ticket status.
 * Always uses text labels in addition to color — never relies on color alone.
 * Includes an ARIA label for assistive technology.
 */
export function StatusBadge({ status, rawLabel, size = 'md' }: StatusBadgeProps) {
  const display = getStatusDisplay(status);
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-2.5 py-1';

  return (
    <span
      role="status"
      aria-label={display.ariaLabel}
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
        <span className="opacity-60 text-xs ml-1">({rawLabel})</span>
      )}
    </span>
  );
}
