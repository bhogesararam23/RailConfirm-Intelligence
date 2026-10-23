'use client';

import React from 'react';
import { toOffsetIso } from '@/lib/validation';
import type { PassengerRowState } from '@/hooks/usePassengerList';

interface PassengerRowProps {
  index: number;
  row: PassengerRowState;
  onChange: (updates: Partial<PassengerRowState>) => void;
  onRemove: () => void;
  canRemove: boolean;
  errors?: Record<string, string>;
}

/**
 * One passenger's inputs.
 *
 * `datetime-local` produces a value with no UTC offset, and the backend refuses a
 * naive timestamp. Rather than sending something ambiguous, the offset of the
 * viewer's own zone is attached before the value is stored.
 *
 * Field errors are linked with aria-describedby and marked with aria-invalid, so a
 * screen-reader user hears which input needs fixing instead of reading a detached
 * paragraph.
 */
export function PassengerRow({
  index,
  row,
  onChange,
  onRemove,
  canRemove,
  errors = {},
}: PassengerRowProps) {
  const baseId = row.rowId;
  const originalId = `${baseId}-original`;
  const currentId = `${baseId}-current`;
  const timeId = `${baseId}-time`;
  const unknownId = `${baseId}-time-unknown`;

  const localTimeValue = row.current_status_observed_at
    ? row.current_status_observed_at.slice(0, 16)
    : '';

  return (
    <div className="rounded-md border border-gray-200 bg-gray-50/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Passenger {index + 1}
        </h3>
        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="rounded text-xs font-medium text-red-600 hover:text-red-800 focus:outline-none focus:ring-2 focus:ring-red-400"
            aria-label={`Remove passenger ${index + 1}`}
          >
            Remove
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor={originalId} className="block text-xs font-medium text-gray-700">
            Status as booked
          </label>
          <input
            id={originalId}
            type="text"
            maxLength={120}
            placeholder="e.g. GNWL/45 or RAC 10"
            autoComplete="off"
            value={row.original_status}
            onChange={(event) => onChange({ original_status: event.target.value })}
            aria-invalid={Boolean(errors.original_status)}
            aria-describedby={errors.original_status ? `${originalId}-error` : undefined}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.original_status && (
            <p id={`${originalId}-error`} className="mt-1 text-xs text-red-600">
              {errors.original_status}
            </p>
          )}
        </div>

        <div>
          <label htmlFor={currentId} className="block text-xs font-medium text-gray-700">
            Current status
          </label>
          <input
            id={currentId}
            type="text"
            maxLength={120}
            placeholder="e.g. GNWL/12 or RAC 3"
            autoComplete="off"
            value={row.current_status}
            onChange={(event) => onChange({ current_status: event.target.value })}
            aria-invalid={Boolean(errors.current_status)}
            aria-describedby={errors.current_status ? `${currentId}-error` : undefined}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.current_status && (
            <p id={`${currentId}-error`} className="mt-1 text-xs text-red-600">
              {errors.current_status}
            </p>
          )}
        </div>

        <div>
          <label htmlFor={timeId} className="block text-xs font-medium text-gray-700">
            When was this observed?
          </label>
          <input
            id={timeId}
            type="datetime-local"
            disabled={row.timeUnknown}
            value={localTimeValue}
            onChange={(event) =>
              onChange({
                current_status_observed_at: toOffsetIso(event.target.value),
              })
            }
            aria-invalid={Boolean(errors.current_status_observed_at)}
            aria-describedby={
              errors.current_status_observed_at ? `${timeId}-error` : undefined
            }
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:text-gray-400"
          />
          <label
            htmlFor={unknownId}
            className="mt-1.5 flex items-center gap-1.5 text-xs text-gray-500"
          >
            <input
              id={unknownId}
              type="checkbox"
              checked={row.timeUnknown}
              onChange={(event) =>
                onChange({
                  timeUnknown: event.target.checked,
                  current_status_observed_at: event.target.checked
                    ? null
                    : row.current_status_observed_at,
                })
              }
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            I don&apos;t know when this was observed
          </label>
          {errors.current_status_observed_at && (
            <p id={`${timeId}-error`} className="mt-1 text-xs text-red-600">
              {errors.current_status_observed_at}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
