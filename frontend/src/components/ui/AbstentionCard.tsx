import { ABSTENTION_MESSAGES } from '@/lib/types';

interface AbstentionCardProps {
  reason?: string;
  /** Additional context to show below the main message */
  context?: string;
}

/**
 * Displayed whenever is_supported is false.
 * Shows a clear, jargon-free explanation of why an estimate is unavailable.
 * Never shows a fake probability.
 */
export function AbstentionCard({ reason, context }: AbstentionCardProps) {
  const message =
    (reason && ABSTENTION_MESSAGES[reason]) ||
    ABSTENTION_MESSAGES.no_trained_model;

  const suggestion = getSuggestion(reason);

  return (
    <div
      role="status"
      aria-label="Estimate not available"
      className="rounded-lg border border-gray-200 bg-gray-50 p-4 space-y-2"
    >
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="mt-0.5 text-xl text-gray-400">
          ⚠
        </span>
        <div className="space-y-1">
          <h3 className="font-semibold text-gray-800 text-sm">
            Estimate not available
          </h3>
          <p className="text-sm text-gray-600">{message}</p>
          {context && (
            <p className="text-sm text-gray-500 italic">{context}</p>
          )}
          {suggestion && (
            <p className="text-sm text-gray-500">{suggestion}</p>
          )}
        </div>
      </div>
    </div>
  );
}

function getSuggestion(reason?: string): string | null {
  switch (reason) {
    case 'no_trained_model':
      return 'This estimate will be available once a validated model has been trained on approved historical data.';
    case 'unsupported_status':
      return 'Try entering the status code exactly as shown on your ticket (e.g. GNWL/45, PQWL/12).';
    case 'unsupported_class':
      return 'Support for additional travel classes will be added as validated training data becomes available.';
    case 'insufficient_sample':
      return 'More historical records for this ticket category are needed before a reliable estimate can be produced.';
    case 'unknown_status':
      return 'Check that the status format matches what appears on your ticket or the IRCTC app (e.g. GNWL/45, RAC 3, CNF).';
    default:
      return null;
  }
}
