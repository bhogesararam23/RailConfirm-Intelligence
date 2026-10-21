'use client';

import React from 'react';
import type { PassengerInput } from '@/lib/types';

interface PassengerRowProps {
  index: number;
  passenger: PassengerInput;
  onChange: (updates: Partial<PassengerInput>) => void;
  onRemove: () => void;
  canRemove: boolean;
  errors?: Record<string, string>;
}

export function PassengerRow({
  index,
  passenger,
  onChange,
  onRemove,
  canRemove,
  errors = {},
}: PassengerRowProps) {
  return (
    <div className="relative rounded-md border border-gray-200 bg-gray-50/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Passenger {index + 1}
        </span>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-xs text-red-600 hover:text-red-800"
            aria-label={`Remove passenger ${index + 1}`}
          >
            Remove
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label
            htmlFor={`p_${index}_orig`}
            className="block text-xs font-medium text-gray-700"
          >
            Original Status (as booked)
          </label>
          <input
            id={`p_${index}_orig`}
            type="text"
            placeholder="e.g. GNWL/45 or RAC 10"
            value={passenger.original_status}
            onChange={(e) => onChange({ original_status: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.original_status && (
            <p className="mt-1 text-xs text-red-600">{errors.original_status}</p>
          )}
        </div>

        <div>
          <label
            htmlFor={`p_${index}_curr`}
            className="block text-xs font-medium text-gray-700"
          >
            Current Status (latest observed)
          </label>
          <input
            id={`p_${index}_curr`}
            type="text"
            placeholder="e.g. GNWL/12 or RAC 3"
            value={passenger.current_status}
            onChange={(e) => onChange({ current_status: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.current_status && (
            <p className="mt-1 text-xs text-red-600">{errors.current_status}</p>
          )}
        </div>

        <div>
          <label
            htmlFor={`p_${index}_time`}
            className="block text-xs font-medium text-gray-700"
          >
            Observation Timestamp (Optional)
          </label>
          <input
            id={`p_${index}_time`}
            type="datetime-local"
            disabled={passenger.status_time_unknown}
            value={passenger.current_status_observed_at || ''}
            onChange={(e) => onChange({ current_status_observed_at: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm disabled:bg-gray-100 disabled:text-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <label className="mt-1.5 flex items-center gap-1.5 text-xs text-gray-500">
            <input
              type="checkbox"
              checked={passenger.status_time_unknown || false}
              onChange={(e) =>
                onChange({
                  status_time_unknown: e.target.checked,
                  current_status_observed_at: e.target.checked ? undefined : passenger.current_status_observed_at,
                })
              }
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            Time unknown / unrecorded
          </label>
        </div>
      </div>
    </div>
  );
}
