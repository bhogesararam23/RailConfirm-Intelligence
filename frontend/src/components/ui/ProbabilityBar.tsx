import { formatProbability } from '@/lib/statusUtils';

interface ProbabilityBarProps {
  p_cnf: number | null;
  p_rac: number | null;
  p_wl: number | null;
  p_other: number | null;
}

/**
 * Horizontal stacked bar showing probability breakdown across CNF / RAC / WL / Other.
 * Only rendered when the prediction is supported (is_supported === true).
 * Includes percentage text labels and ARIA description — not color-only.
 */
export function ProbabilityBar({
  p_cnf,
  p_rac,
  p_wl,
  p_other,
}: ProbabilityBarProps) {
  const cnf = p_cnf ?? 0;
  const rac = p_rac ?? 0;
  const wl = p_wl ?? 0;
  const other = p_other ?? 0;

  const segments: { label: string; value: number; barClass: string; textClass: string }[] = [
    { label: 'CNF', value: cnf, barClass: 'bg-green-500', textClass: 'text-green-800' },
    { label: 'RAC', value: rac, barClass: 'bg-yellow-400', textClass: 'text-yellow-800' },
    { label: 'WL', value: wl, barClass: 'bg-orange-400', textClass: 'text-orange-800' },
    { label: 'Other', value: other, barClass: 'bg-gray-300', textClass: 'text-gray-600' },
  ].filter((s) => s.value > 0);

  const ariaDesc = segments
    .map((s) => `${s.label}: ${formatProbability(s.value)}`)
    .join(', ');

  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div
        role="img"
        aria-label={`Probability breakdown — ${ariaDesc}`}
        className="flex h-6 w-full overflow-hidden rounded-full border border-gray-200 bg-gray-100"
      >
        {segments.map((s) => (
          <div
            key={s.label}
            title={`${s.label}: ${formatProbability(s.value)}`}
            style={{ width: `${s.value * 100}%` }}
            className={`${s.barClass} flex items-center justify-center`}
          />
        ))}
      </div>

      {/* Text legend */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {segments.map((s) => (
          <span key={s.label} className={`flex items-center gap-1 font-medium ${s.textClass}`}>
            <span aria-hidden="true">■</span>
            {s.label}: {formatProbability(s.value)}
          </span>
        ))}
      </div>

      {/* Mandatory disclaimer */}
      <p className="text-xs text-gray-500 italic">
        Estimated probability — not a guarantee. Based on historical patterns; individual outcomes may differ.
      </p>
    </div>
  );
}
