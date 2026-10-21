'use client';

import React from 'react';
import { CLASS_CODES, QUOTA_CODES, type JourneyInput } from '@/lib/types';

interface JourneyFormProps {
  value: JourneyInput;
  onChange: (updates: Partial<JourneyInput>) => void;
  errors?: Record<string, string>;
}

export function JourneyForm({ value, onChange, errors = {} }: JourneyFormProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="mb-4 text-base font-semibold text-gray-900">Journey Details</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label htmlFor="train_number" className="block text-xs font-medium text-gray-700">
            Train Number
          </label>
          <input
            id="train_number"
            type="text"
            maxLength={6}
            placeholder="e.g. 12301"
            value={value.train_number}
            onChange={(e) => onChange({ train_number: e.target.value.trim() })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.train_number && (
            <p className="mt-1 text-xs text-red-600">{errors.train_number}</p>
          )}
        </div>

        <div>
          <label htmlFor="journey_date" className="block text-xs font-medium text-gray-700">
            Journey Date
          </label>
          <input
            id="journey_date"
            type="date"
            value={value.journey_date}
            onChange={(e) => onChange({ journey_date: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.journey_date && (
            <p className="mt-1 text-xs text-red-600">{errors.journey_date}</p>
          )}
        </div>

        <div>
          <label htmlFor="boarding_station" className="block text-xs font-medium text-gray-700">
            Boarding Station Code
          </label>
          <input
            id="boarding_station"
            type="text"
            maxLength={10}
            placeholder="e.g. NDLS"
            value={value.boarding_station}
            onChange={(e) => onChange({ boarding_station: e.target.value.toUpperCase().trim() })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.boarding_station && (
            <p className="mt-1 text-xs text-red-600">{errors.boarding_station}</p>
          )}
        </div>

        <div>
          <label htmlFor="destination_station" className="block text-xs font-medium text-gray-700">
            Destination Station Code
          </label>
          <input
            id="destination_station"
            type="text"
            maxLength={10}
            placeholder="e.g. HWH"
            value={value.destination_station}
            onChange={(e) => onChange({ destination_station: e.target.value.toUpperCase().trim() })}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm uppercase shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
          {errors.destination_station && (
            <p className="mt-1 text-xs text-red-600">{errors.destination_station}</p>
          )}
        </div>

        <div>
          <label htmlFor="class_code" className="block text-xs font-medium text-gray-700">
            Travel Class
          </label>
          <select
            id="class_code"
            value={value.class_code}
            onChange={(e) => onChange({ class_code: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {Object.entries(CLASS_CODES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
          {errors.class_code && (
            <p className="mt-1 text-xs text-red-600">{errors.class_code}</p>
          )}
        </div>

        <div>
          <label htmlFor="quota_code" className="block text-xs font-medium text-gray-700">
            Quota
          </label>
          <select
            id="quota_code"
            value={value.quota_code}
            onChange={(e) => onChange({ quota_code: e.target.value })}
            className="mt-1 block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {Object.entries(QUOTA_CODES).map(([code, label]) => (
              <option key={code} value={code}>
                {label}
              </option>
            ))}
          </select>
          {errors.quota_code && (
            <p className="mt-1 text-xs text-red-600">{errors.quota_code}</p>
          )}
        </div>
      </div>
    </div>
  );
}
