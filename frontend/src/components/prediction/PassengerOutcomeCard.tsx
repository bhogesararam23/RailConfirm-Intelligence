'use client';

import React from 'react';
import type { PassengerOutcome } from '@/lib/types';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProbabilityBar } from '@/components/ui/ProbabilityBar';
import { AbstentionCard } from '@/components/ui/AbstentionCard';
import { describeBasis, formatProbability } from '@/lib/statusUtils';

interface PassengerOutcomeCardProps {
  index: number;
  outcome: PassengerOutcome;
}

/**
 * One passenger's observed facts and, when supported, their outcome distribution.
 *
 * Observed status and estimate are rendered as separate blocks because they answer
 * different questions: one is what a source reported, the other is what is expected
 * later. A supported outcome always carries all five probabilities or the backend
 * contract is broken, so the render keys off `is_supported` and never guesses from a
 * null.
 */
export function PassengerOutcomeCard({ index, outcome }: PassengerOutcomeCardProps) {
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
            CNF and RAC are distinct outcomes: a confirmed berth is full accommodation,
            RAC authorises seated travel. These are not the same thing and are not added
            together here.
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
