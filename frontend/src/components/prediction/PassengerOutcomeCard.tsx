'use client';

import React from 'react';
import type { PassengerOutcome, PredictionTarget } from '@/lib/types';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProbabilityBar } from '@/components/ui/ProbabilityBar';
import { AbstentionCard } from '@/components/ui/AbstentionCard';
import { describeBasis, formatProbability } from '@/lib/statusUtils';

interface PassengerOutcomeCardProps {
  index: number;
  outcome: PassengerOutcome;
  /** The target the report answers, so the headline figure names its own event. */
  target: PredictionTarget;
}

const TARGET_EVENT_LABELS: Record<PredictionTarget, string> = {
  final_chart_cnf: 'Chance of a confirmed berth',
  final_chart_cnf_or_rac: 'Chance of CNF or RAC',
};

const TARGET_EVENT_NOTES: Record<PredictionTarget, string> = {
  final_chart_cnf:
    'The probability of the confirmed class alone. RAC and waitlisted outcomes are real possibilities that this figure does not count.',
  final_chart_cnf_or_rac:
    'The sum of the CNF and RAC classes — the event this target asks for. The distribution below keeps the two apart, because a berth and a RAC seat are different outcomes.',
};

/**
 * One passenger's observed facts and, when supported, their outcome distribution.
 *
 * Observed status and estimate are rendered as separate blocks because they answer
 * different questions: one is what a source reported, the other is what is expected
 * later. A supported outcome always carries all five probabilities or the backend
 * contract is broken, so the render keys off `is_supported` and never guesses from a
 * null.
 *
 * The headline is the target's own event, taken from the server's `p_target_event`
 * rather than added up in the browser: a client that summed two classes itself would be
 * a second implementation of the number the evaluation scores. The five-class
 * distribution stays beside it, because the headline is a sum over classes and a reader
 * is entitled to see the parts.
 */
export function PassengerOutcomeCard({ index, outcome, target }: PassengerOutcomeCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2">
        <span className="text-xs font-semibold text-gray-700">
          Passenger {index + 1}
        </span>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-400">As booked:</span>
          <StatusBadge
            status={outcome.original_status_normalized}
            rawLabel={outcome.original_status}
            size="sm"
          />
          <span className="text-xs text-gray-400">Observed now:</span>
          <StatusBadge
            status={outcome.current_status_normalized}
            rawLabel={outcome.current_status}
            size="sm"
          />
        </div>
      </div>

      {outcome.parse_warnings.length > 0 && (
        <ul className="mb-3 space-y-1 rounded bg-amber-50 p-2 text-xs text-amber-800">
          {outcome.parse_warnings.map((warning, i) => (
            <li key={i}>{warning}</li>
          ))}
        </ul>
      )}

      {outcome.is_supported ? (
        <div className="space-y-3">
          <div className="rounded-md border border-blue-100 bg-blue-50/60 p-3">
            <p className="text-xs font-medium text-gray-700">
              {TARGET_EVENT_LABELS[target]}
            </p>
            <p className="text-2xl font-bold text-gray-900" data-testid="target-event-probability">
              {formatProbability(outcome.p_target_event)}
            </p>
            <p className="mt-1 text-[11px] text-gray-600">{TARGET_EVENT_NOTES[target]}</p>
          </div>

          <ProbabilityBar
            p_cnf={outcome.p_cnf}
            p_rac={outcome.p_rac}
            p_wl={outcome.p_wl}
            p_cancelled={outcome.p_cancelled}
            p_other={outcome.p_other}
          />

          <dl className="grid grid-cols-2 gap-2 text-center text-xs sm:grid-cols-5">
            {[
              { term: 'Confirmed berth', value: outcome.p_cnf },
              { term: 'RAC', value: outcome.p_rac },
              { term: 'Waitlisted', value: outcome.p_wl },
              { term: 'Cancelled', value: outcome.p_cancelled },
              { term: 'Other', value: outcome.p_other },
            ].map((cell) => (
              <div key={cell.term} className="rounded bg-gray-50 p-2">
                <dd className="block font-bold text-gray-800">
                  {formatProbability(cell.value)}
                </dd>
                <dt className="text-gray-500">{cell.term}</dt>
              </div>
            ))}
          </dl>

          <p className="text-xs text-gray-500">{describeBasis(outcome.basis)}</p>
          <p className="text-[11px] text-gray-400">
            {target === 'final_chart_cnf_or_rac'
              ? 'CNF and RAC are combined only in the figure above, because that is the event this target names. In the distribution they stay separate: a confirmed berth is full accommodation, RAC authorises seated travel.'
              : 'CNF and RAC are distinct outcomes: a confirmed berth is full accommodation, RAC authorises seated travel. RAC is not counted toward the confirmed figure above.'}
          </p>
        </div>
      ) : (
        <AbstentionCard
          reason={outcome.abstention_reason}
          context={
            outcome.current_status_normalized === 'UNKNOWN'
              ? `The status "${outcome.current_status}" is not in the verified mapping.`
              : undefined
          }
        />
      )}
    </div>
  );
}
