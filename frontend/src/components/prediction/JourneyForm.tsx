'use client';

import React from 'react';
import { CLASS_CODES, QUOTA_CODES } from '@/lib/types';
import type { JourneyInput, PredictionTarget } from '@/lib/types';

interface JourneyFormProps {
  value: JourneyInput;
  /** datetime-local value; the page converts it to an offset-aware ISO string. */
  predictionLocalValue: string;
  target: PredictionTarget;
  onChange: (updates: Partial<JourneyInput>) => void;
  onPredictionTimeChange: (localValue: string) => void;
  onTargetChange: (target: PredictionTarget) => void;
  errors?: Record<string, string>;
}

const TARGET_OPTIONS: { value: PredictionTarget; label: string; hint: string }[] = [
  {
    value: 'final_chart_cnf',
    label: 'Confirmed berth at final chart',
    hint: 'What counts: a full berth when the final chart is prepared.',
  },
  {
    value: 'final_chart_cnf_or_rac',
    label: 'CNF or RAC at final chart',
    hint: 'What counts: travelling, seated at worst, at final chart.',
  },
];

function fieldProps(errors: Record<string, string>, key: string) {
  const message = errors[key];
  return {
    'aria-invalid': Boolean(message),
    'aria-describedby': message ? `${key}-error` : undefined,
  };
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-1 text-xs text-red-600">
      {message}
    </p>
  );
}

/**
 * Journey and prediction-context inputs.
 *
 * The prediction moment and target are part of the request, not assumptions made on
 * the user's behalf: the same booking means different things for a CNF target and a
 * CNF-or-RAC target, and an estimate is only interpretable next to the time it was
 * made from.
 */
export function JourneyForm({
  value,
  predictionLocalValue,
  target,
  onChange,
  onPredictionTimeChange,
  onTargetChange,
  errors = {},
}: JourneyFormProps) {
  const activeTarget = TARGET_OPTIONS.find((option) => option.value === target);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-1 text-base font-semibold text-gray-900">Journey details</h2>
      <p className="mb-4 text-xs text-gray-500">
        Everything here describes the booking as you know it. Passenger names are
        never needed.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor="train_number" className="block text-xs font-medium text-gray-700">
            Train number
          </label>
          <input
            id="train_number"
            type="text"
            inputMode="numeric"
            maxLength={6}
            placeholder="e.g. 12301"
            autoComplete="off"
            value={value.train_number}
            onChange={(event) => onChange({ train_number: event.target.value })}
            {...fieldProps(errors, 'train_number')}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <FieldError id="train_number-error" message={errors.train_number} />
        </div>

        <div>
          <label htmlFor="journey_date" className="block text-xs font-medium text-gray-700">
            Journey date
          </label>
          <input
            id="journey_date"
            type="date"
            value={value.journey_date}
            onChange={(event) => onChange({ journey_date: event.target.value })}
            {...fieldProps(errors, 'journey_date')}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <FieldError id="journey_date-error" message={errors.journey_date} />
        </div>

        <div>
          <label htmlFor="boarding_station" className="block text-xs font-medium text-gray-700">
            Boarding station code
          </label>
          <input
            id="boarding_station"
            type="text"
            maxLength={10}
            placeholder="e.g. NDLS"
            autoComplete="off"
            value={value.boarding_station}
            onChange={(event) =>
              onChange({ boarding_station: event.target.value.toUpperCase() })
            }
            {...fieldProps(errors, 'boarding_station')}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <FieldError id="boarding_station-error" message={errors.boarding_station} />
        </div>

        <div>
          <label
            htmlFor="destination_station"
            className="block text-xs font-medium text-gray-700"
          >
            Destination station code
          </label>
          <input
            id="destination_station"
            type="text"
            maxLength={10}
            placeholder="e.g. HWH"
            autoComplete="off"
            value={value.destination_station}
            onChange={(event) =>
              onChange({ destination_station: event.target.value.toUpperCase() })
            }
            {...fieldProps(errors, 'destination_station')}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <FieldError id="destination_station-error" message={errors.destination_station} />
        </div>

        <div>
          <label htmlFor="class_code" className="block text-xs font-medium text-gray-700">
            Travel class
          </label>
          <select
            id="class_code"
            value={value.class_code}
            onChange={(event) => onChange({ class_code: event.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {Object.entries(CLASS_CODES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
          <FieldError id="class_code-error" message={errors.class_code} />
        </div>

        <div>
          <label htmlFor="quota_code" className="block text-xs font-medium text-gray-700">
            Quota
          </label>
          <select
            id="quota_code"
            value={value.quota_code}
            onChange={(event) => onChange({ quota_code: event.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {Object.entries(QUOTA_CODES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
          <FieldError id="quota_code-error" message={errors.quota_code} />
        </div>

        <div>
          <label htmlFor="prediction_at" className="block text-xs font-medium text-gray-700">
            Estimating as of
          </label>
          <input
            id="prediction_at"
            type="datetime-local"
            value={predictionLocalValue}
            onChange={(event) => onPredictionTimeChange(event.target.value)}
            {...fieldProps(errors, 'prediction_at')}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          <p className="mt-1 text-[11px] text-gray-500">
            Sent with your browser&apos;s UTC offset. Must be before the journey date.
          </p>
          <FieldError id="prediction_at-error" message={errors.prediction_at} />
        </div>

        <fieldset className="sm:col-span-2">
          <legend className="block text-xs font-medium text-gray-700">
            What are we estimating?
          </legend>
          <div className="mt-1 space-y-1">
            {TARGET_OPTIONS.map((option) => (
              <label
                key={option.value}
                className="flex items-start gap-2 text-xs text-gray-700"
              >
                <input
                  type="radio"
                  name="target"
                  value={option.value}
                  checked={target === option.value}
                  onChange={() => onTargetChange(option.value)}
                  className="mt-0.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>
          {activeTarget && (
            <p className="mt-1 text-[11px] text-gray-500">{activeTarget.hint}</p>
          )}
          <FieldError id="target-error" message={errors.target} />
        </fieldset>
      </div>
    </div>
  );
}
