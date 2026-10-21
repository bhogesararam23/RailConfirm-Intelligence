'use client';

import React, { useState } from 'react';
import type { JourneyInput, PredictionRequest } from '@/lib/types';
import { usePassengerList } from '@/hooks/usePassengerList';
import { usePrediction } from '@/hooks/usePrediction';
import { validateJourney, validatePassengers } from '@/lib/validation';
import { JourneyForm } from '@/components/prediction/JourneyForm';
import { PassengerList } from '@/components/prediction/PassengerList';
import { PredictionResult } from '@/components/prediction/PredictionResult';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorBanner } from '@/components/ui/ErrorBanner';

const initialJourney: JourneyInput = {
  train_number: '12301',
  journey_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
  boarding_station: 'NDLS',
  destination_station: 'HWH',
  class_code: 'SL',
  quota_code: 'GN',
};

export default function HomePage() {
  const [journey, setJourney] = useState<JourneyInput>(initialJourney);
  const { passengers, addPassenger, removePassenger, updatePassenger, canAddMore } =
    usePassengerList();
  const { state, result, error, submit, reset } = usePrediction();

  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  const handleJourneyChange = (updates: Partial<JourneyInput>) => {
    setJourney((prev) => ({ ...prev, ...updates }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const jVal = validateJourney(journey);
    const pVal = validatePassengers(passengers);

    const mergedErrors: Record<string, string> = {
      ...jVal.errors,
      ...pVal.errors,
    };

    if (!jVal.isValid || !pVal.isValid) {
      setValidationErrors(mergedErrors);
      return;
    }

    setValidationErrors({});

    const request: PredictionRequest = {
      journey,
      prediction_at: new Date().toISOString(),
      passengers,
    };

    await submit(request);
  };

  // Convert passenger indexed errors for PassengerList
  const passengerErrors: Record<number, Record<string, string>> = {};
  Object.entries(validationErrors).forEach(([key, msg]) => {
    const match = key.match(/^passengers\[(\d+)\]\.(.+)$/);
    if (match) {
      const pIdx = parseInt(match[1], 10);
      const field = match[2];
      if (!passengerErrors[pIdx]) passengerErrors[pIdx] = {};
      passengerErrors[pIdx][field] = msg;
    }
  });

  return (
    <div className="space-y-8">
      {/* Introduction Hero */}
      <div className="border-b border-gray-200 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
          Estimate Railway Confirmation Likelihood
        </h1>
        <p className="mt-2 text-sm text-gray-600 max-w-2xl">
          Evidence-driven intelligence for Indian Railways Waitlist (WL) and RAC tickets.
          Evaluates individual and joint group outcomes at final chart preparation without third-party APIs.
        </p>
      </div>

      {error && (
        <ErrorBanner
          message={error}
          onDismiss={() => {}}
        />
      )}

      {state === 'success' && result ? (
        <PredictionResult result={result} onReset={reset} />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          <JourneyForm
            value={journey}
            onChange={handleJourneyChange}
            errors={validationErrors}
          />

          <PassengerList
            passengers={passengers}
            onAdd={addPassenger}
            onRemove={removePassenger}
            onChange={updatePassenger}
            canAdd={canAddMore}
            errors={passengerErrors}
          />

          <div className="flex items-center justify-between pt-2">
            <span className="text-xs text-gray-500">
              Operates fully local-first. No ticket data leaves your environment.
            </span>
            <button
              type="submit"
              disabled={state === 'loading'}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-blue-400"
            >
              {state === 'loading' ? (
                <>
                  <LoadingSpinner size="sm" />
                  Calculating...
                </>
              ) : (
                'Estimate Confirmation Likelihood'
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
