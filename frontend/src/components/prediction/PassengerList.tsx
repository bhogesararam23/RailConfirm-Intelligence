'use client';

import React from 'react';
import type { PassengerInput } from '@/lib/types';
import { PassengerRow } from './PassengerRow';

interface PassengerListProps {
  passengers: PassengerInput[];
  onAdd: () => void;
  onRemove: (index: number) => void;
  onChange: (index: number, updates: Partial<PassengerInput>) => void;
  canAdd: boolean;
  errors?: Record<number, Record<string, string>>;
}

export function PassengerList({
  passengers,
  onAdd,
  onRemove,
  onChange,
  canAdd,
  errors = {},
}: PassengerListProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            Passenger Reservation Status ({passengers.length})
          </h2>
          <p className="text-xs text-gray-500">
            Enter original and current waitlist or RAC status for each passenger. No names required.
          </p>
        </div>
        {canAdd && (
          <button
            type="button"
            onClick={onAdd}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            + Add Passenger
          </button>
        )}
      </div>

      <div className="space-y-3">
        {passengers.map((passenger, idx) => (
          <PassengerRow
            key={idx}
            index={idx}
            passenger={passenger}
            onChange={(updates) => onChange(idx, updates)}
            onRemove={() => onRemove(idx)}
            canRemove={passengers.length > 1}
            errors={errors[idx] || {}}
          />
        ))}
      </div>
    </div>
  );
}
