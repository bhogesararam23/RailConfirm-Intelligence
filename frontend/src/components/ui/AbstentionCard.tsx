import { ABSTENTION_MESSAGES } from '@/lib/types';
import type { AbstentionReason } from '@/lib/types';

interface AbstentionCardProps {
  reason: AbstentionReason | null | undefined;
  /** Additional context, e.g. the raw status the server could not classify. */
  context?: string;
}

/**
 * Shown whenever `is_supported` is false. Never renders a probability.
 *
 * An unrecognised reason code reports that the client is out of date rather than
 * falling back to the "no trained model" text: showing the wrong reason is worse
 * than admitting the mismatch, because the user would act on advice meant for a
 * different problem.
 */
export function AbstentionCard({ reason, context }: AbstentionCardProps) {
  const known = reason !== null && reason !== undefined && reason in ABSTENTION_MESSAGES;
  const message = known
    ? ABSTENTION_MESSAGES[reason as AbstentionReason]
    : 'The system declined to estimate and reported a reason this version of the interface does not recognise. The technical reason is shown below.';

  return (
    <div
      role="status"
      aria-label="Estimate not available"
      className="space-y-2 rounded-lg border border-gray-200 bg-gray-50 p-4"
    >
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="mt-0.5 text-xl text-gray-400">
          ⓘ
        </span>
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-gray-800">
            No estimate for this booking
          </h3>
          <p className="text-sm text-gray-600">{message}</p>
          {context && <p className="text-sm italic text-gray-500">{context}</p>}
          {reason && (
            <p className="text-xs text-gray-500">
              Reason code:{' '}
              <code className="rounded bg-white px-1 py-0.5 font-mono">{reason}</code>
            </p>
          )}
          {!known && (
            <p className="text-xs text-amber-700">
              If this persists, the backend may be newer than this interface.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
