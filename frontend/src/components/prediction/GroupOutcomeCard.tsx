'use client';

import React from 'react';
import type { GroupOutcome } from '@/lib/types';
import { AbstentionCard } from '@/components/ui/AbstentionCard';
import { formatProbability } from '@/lib/statusUtils';

interface GroupOutcomeCardProps {
  group: GroupOutcome;
  passengerCount: number;
}

/**
 * Joint outcomes for a booking group.
 *
 * The assumption text is shown whether or not the estimate succeeded: an
 * independence baseline is a provisional approximation, and passengers sharing a
 * booking, queue and quota are not independent, so the number only means something
 * together with that caveat.
 */
export function GroupOutcomeCard({ group, passengerCount }: GroupOutcomeCardProps) {
  const methodLabel =
    group.method === 'independence_baseline'
      ? 'Independence baseline (approximation)'
      : group.method === 'single_passenger'
        ? 'Single passenger'
        : group.method === 'insufficient_data'
          ? 'Not computed'
          : group.method;

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-blue-100 pb-2">
        <div>
          <h3 className="text-sm font-semibold text-blue-950">
            Group outcomes ({passengerCount}{' '}
            {passengerCount === 1 ? 'passenger' : 'passengers'})
          </h3>
          <p className="text-xs text-blue-700">
            Joint probabilities for the booking as a whole.
          </p>
        </div>
        <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
          Method: {methodLabel}
        </span>
      </div>

      {group.is_supported ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              {
                value: group.p_all_cnf,
                title: 'All passengers confirmed',
                detail: 'Every passenger holds a full berth at the deadline.',
              },
              {
                value: group.p_all_cnf_or_rac,
                title: 'All CNF or RAC',
                detail: 'Every passenger travels, seated at worst.',
              },
              {
                value: group.p_at_least_one_wl,
                title: 'At least one remains waitlisted',
                detail: 'One or more passengers are still unconfirmed.',
              },
            ].map((cell) => (
              <div
                key={cell.title}
                className="rounded-md border border-emerald-100 bg-white p-3 text-center"
              >
                <span className="block text-xl font-bold text-gray-800">
                  {formatProbability(cell.value)}
                </span>
                <span className="block text-xs font-medium text-gray-900">
                  {cell.title}
                </span>
                <span className="block text-[10px] text-gray-500">{cell.detail}</span>
              </div>
            ))}
          </div>

          <p className="text-[11px] text-gray-500">
            These three events are not mutually exclusive and do not sum to 100%.
          </p>
        </div>
      ) : (
        <AbstentionCard
          reason={group.abstention_reason}
          context="A group estimate needs every passenger's own estimate; one abstention is enough to withhold the joint figure."
        />
      )}

      <div className="mt-3 rounded border border-blue-100 bg-white/80 p-2.5 text-xs text-gray-600">
        <span className="font-semibold text-gray-800">Assumption: </span>
        {group.assumptions}
      </div>
    </div>
  );
}
