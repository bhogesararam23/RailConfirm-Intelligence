import { formatProbability } from '@/lib/statusUtils';

interface ProbabilityBarProps {
  p_cnf: number | null;
  p_rac: number | null;
  p_wl: number | null;
  p_cancelled: number | null;
  p_other: number | null;
}

/**
 * Stacked distribution over the full outcome space the backend declares:
 * CNF, RAC, WL, CANCELLED, OTHER.
 *
 * All five are rendered. Dropping a class — as the earlier version did with
 * CANCELLED — makes the bar sum to less than 100% while the legend still reads as a
 * complete breakdown, which contradicts the response's own `outcome_classes`.
 *
 * Only called for a supported outcome, so a null here is a contract violation
 * rather than an abstention, and it renders as a dash instead of a zero-width bar.
 */
export function ProbabilityBar({
  p_cnf,
  p_rac,
  p_wl,
  p_cancelled,
  p_other,
}: ProbabilityBarProps) {
  const segments = [
    { label: 'CNF', long: 'Confirmed berth', value: p_cnf, barClass: 'bg-green-500', textClass: 'text-green-800' },
    { label: 'RAC', long: 'RAC accommodation', value: p_rac, barClass: 'bg-yellow-400', textClass: 'text-yellow-800' },
    { label: 'WL', long: 'Remains waitlisted', value: p_wl, barClass: 'bg-orange-400', textClass: 'text-orange-800' },
    { label: 'CAN', long: 'Cancelled', value: p_cancelled, barClass: 'bg-red-400', textClass: 'text-red-800' },
    { label: 'Other', long: 'Other outcome', value: p_other, barClass: 'bg-gray-400', textClass: 'text-gray-700' },
  ];

  const ariaDescription = segments
    .map((segment) => `${segment.long}: ${formatProbability(segment.value)}`)
    .join(', ');

  return (
    <div className="space-y-2">
      <div
        role="img"
        aria-label={`Probability breakdown across the declared outcome classes — ${ariaDescription}`}
        className="flex h-6 w-full overflow-hidden rounded-full border border-gray-200 bg-gray-100"
      >
        {segments.map((segment) => {
          const width = segment.value ?? 0;
          if (width <= 0) return null;
          return (
            <div
              key={segment.label}
              title={`${segment.long}: ${formatProbability(segment.value)}`}
              style={{ width: `${width * 100}%` }}
              className={`${segment.barClass} flex items-center justify-center`}
            />
          );
        })}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {segments.map((segment) => (
          <li
            key={segment.label}
            className={`flex items-center gap-1 font-medium ${segment.textClass}`}
          >
            <span aria-hidden="true">■</span>
            {segment.long}: {formatProbability(segment.value)}
          </li>
        ))}
      </ul>

      <p className="text-xs text-gray-500 italic">
        Estimated probability, not a guarantee. These figures are not calibrated
        unless the response says otherwise.
      </p>
    </div>
  );
}
