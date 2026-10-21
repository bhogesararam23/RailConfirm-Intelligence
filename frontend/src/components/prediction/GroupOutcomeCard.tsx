'use client';

import React from 'react';
import type { GroupOutcome } from '@/lib/types';
import { AbstentionCard } from '@/components/ui/AbstentionCard';

interface GroupOutcomeCardProps {
  group: GroupOutcome;
  passengerCount: number;
}

export function GroupOutcomeCard({ group, passengerCount }: GroupOutcomeCardProps) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/30 p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between border-b border-blue-100 pb-2">
        <div>
          <h3 className="text-sm font-semibold text-blue-950">
            Group Joint Outcomes ({passengerCount} Passengers)
          </h3>
          <p className="text-xs text-blue-700">
            Joint probability estimates for the booking group as a whole.
          </p>
        </div>
        <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
          Method: {group.method}
        </span>
      </div>

      {group.is_supported && group.p_all_cnf !== null ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-md border border-emerald-200 bg-white p-3 text-center">
              <span className="block text-xl font-bold text-emerald-700">
                {(group.p_all_cnf * 100).toFixed(1)}%
              </span>
              <span className="text-xs font-medium text-emerald-900">
                All Passengers Confirmed
              </span>
              <span className="block text-[10px] text-gray-500">
                Every passenger receives full berth
              </span>
            </div>

            <div className="rounded-md border border-amber-200 bg-white p-3 text-center">
              <span className="block text-xl font-bold text-amber-700">
                {((group.p_all_cnf_or_rac || 0) * 100).toFixed(1)}%
              </span>
              <span className="text-xs font-medium text-amber-900">
                All CNF or RAC
              </span>
              <span className="block text-[10px] text-gray-500">
                All passengers board train
              </span>
            </div>

            <div className="rounded-md border border-orange-200 bg-white p-3 text-center">
              <span className="block text-xl font-bold text-orange-700">
                {((group.p_at_least_one_wl || 0) * 100).toFixed(1)}%
              </span>
              <span className="text-xs font-medium text-orange-900">
                At Least 1 Remains WL
              </span>
              <span className="block text-[10px] text-gray-500">
                At least one passenger left unconfirmed
              </span>
            </div>
          </div>

          <div className="rounded bg-white/80 p-2.5 text-xs text-gray-600 border border-blue-100">
            <span className="font-semibold text-gray-800">Assumption note: </span>
            {group.assumptions}
          </div>
        </div>
      ) : (
        <AbstentionCard reason={group.abstention_reason} />
      )}
    </div>
  );
}
