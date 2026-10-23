'use client';

import React from 'react';
import { MAX_PASSENGERS } from '@/lib/types';
import { PassengerRow } from './PassengerRow';
import type { PassengerRowState } from '@/hooks/usePassengerList';

interface PassengerListProps {
  rows: PassengerRowState[];
  onAdd: () => void;
  onRemove: (rowId: string) => void;
  onChange: (rowId: string, updates: Partial<PassengerRowState>) => void;
  limitReached: boolean;
  errors?: Record<number, Record<string, string>>;
}

/**
 * Passenger rows and the control that adds them.
 *
 * At the limit the button stays visible and disabled with a stated reason. It used
 * to disappear, which reads as a broken control rather than a documented bound.
 */
export function PassengerList({
  rows,
  onAdd,
  onRemove,
  onChange,
  limitReached,
  errors = {},
}: PassengerListProps) {
  const indexOfRow = (rowId: string) => rows.findIndex((row) => row.rowId === rowId);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-gray-900">
            Passenger statuses ({rows.length})
          </h2>
          <p className="text-xs text-gray-500">
            Enter the status as booked and the latest observed status for each
            passenger. Passenger names are not collected.
          </p>
        </div>
        <button
          type="button"
          onClick={onAdd}
          disabled={limitReached}
          aria-describedby={limitReached ? 'passenger-limit-note' : undefined}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
        >
          + Add passenger
        </button>
      </div>

      {limitReached && (
        <p id="passenger-limit-note" className="mb-3 text-xs text-gray-500">
          {MAX_PASSENGERS} passengers is the maximum for one booking group in this
          request.
        </p>
      )}

      <div className="space-y-3">
        {rows.map((row, index) => (
          <PassengerRow
            key={row.rowId}
            index={index}
            row={row}
            onChange={(updates) => onChange(row.rowId, updates)}
            onRemove={() => onRemove(row.rowId)}
            canRemove={rows.length > 1}
            errors={errors[index] || {}}
          />
        ))}
      </div>
    </div>
  );
}
