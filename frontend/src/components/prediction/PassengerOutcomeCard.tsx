'use client';

import React from 'react';
import type { PassengerOutcome } from '@/lib/types';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { ProbabilityBar } from '@/components/ui/ProbabilityBar';
import { AbstentionCard } from '@/components/ui/AbstentionCard';

interface PassengerOutcomeCardProps {
  index: number;
  outcome: PassengerOutcome;
}

export function PassengerOutcomeCard({ index, outcome }: PassengerOutcomeCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between border-b border-gray-100 pb-2">
        <span className="text-xs font-semibold text-gray-700">
          Passenger {index + 1}
        </span>
        {outcome.observed_status && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">Observed:</span>
            <StatusBadge
              status={outcome.observed_status.normalized}
              rawLabel={outcome.observed_status.raw}
              size="sm"
            />
          </div>
        )}
      </div>

      {outcome.is_supported && outcome.p_cnf !== null ? (
        <div className="space-y-3">
          <ProbabilityBar
            p_cnf={outcome.p_cnf}
            p_rac={outcome.p_rac}
            p_wl={outcome.p_wl}
            p_other={outcome.p_other}
          />
          <div className="grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded bg-emerald-50 p-2">
              <span className="block font-bold text-emerald-800">
                {(outcome.p_cnf * 100).toFixed(1)}%
              </span>
              <span className="text-emerald-600">Confirmed Berth</span>
            </div>
            <div className="rounded bg-amber-50 p-2">
              <span className="block font-bold text-amber-800">
                {((outcome.p_rac || 0) * 100).toFixed(1)}%
              </span>
              <span className="text-amber-600">RAC Accommodation</span>
            </div>
            <div className="rounded bg-orange-50 p-2">
              <span className="block font-bold text-orange-800">
                {((outcome.p_wl || 0) * 100).toFixed(1)}%
              </span>
              <span className="text-orange-600">Remains WL</span>
            </div>
          </div>
          <p className="text-[11px] text-gray-400">
            CNF and RAC are distinct outcomes. A confirmed berth provides full accommodation; RAC provides seated travel authorization.
          </p>
        </div>
      ) : (
        <AbstentionCard reason={outcome.abstention_reason} />
      )}
    </div>
  );
}
