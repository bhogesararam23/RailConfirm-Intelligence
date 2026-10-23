'use client';

import React, { useMemo, useState } from 'react';
import { MAX_PASSENGERS } from '@/lib/types';
import type { JourneyInput, PredictionRequest, PredictionTarget } from '@/lib/types';
import { usePassengerList, toPassengerInputs } from '@/hooks/usePassengerList';
import { usePrediction } from '@/hooks/usePrediction';
import { serverFieldToLocalKey, toOffsetIso, validateJourney, validatePassengers } from '@/lib/validation';
import { configuredApiUrl, isLoopbackApi } from '@/lib/api';
import { JourneyForm } from '@/components/prediction/JourneyForm';
import { PassengerList } from '@/components/prediction/PassengerList';
import { PredictionResult } from '@/components/prediction/PredictionResult';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorBanner } from '@/components/ui/ErrorBanner';

/** Example values so the form is usable immediately. They are labelled as examples. */
const EXAMPLE_JOURNEY: JourneyInput = {
  train_number: '12301',
  journey_date: '',
  boarding_station: 'NDLS',
  destination_station: 'HWH',
  class_code: 'SL',
  quota_code: 'GN',
};

function defaultJourney(): JourneyInput {
  const inSevenDays = new Date(Date.now() + 7 * 86_400_000);
  return {
    ...EXAMPLE_JOURNEY,
    journey_date: inSevenDays.toISOString().slice(0, 10),
  };
}

/** datetime-local default: 24 hours from now, in the viewer's zone. */
function defaultPredictionLocal(): string {
  const when = new Date(Date.now() + 86_400_000);
  const local = new Date(when.getTime() - when.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export default function HomePage() {
  const [journey, setJourney] = useState<JourneyInput>(defaultJourney);
  const [predictionLocal, setPredictionLocal] = useState<string>(defaultPredictionLocal);
  const [target, setTarget] = useState<PredictionTarget>('final_chart_cnf');
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({});
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const { rows, addRow, removeRow, updateRow, resetRows, limitReached } =
    usePassengerList();
  const { state, result, failure, submit, reset } = usePrediction();

  const predictionAt = useMemo(
    () => toOffsetIso(predictionLocal),
    [predictionLocal],
  );

  const mergedErrors = useMemo(
    () => ({ ...localErrors, ...serverErrors }),
    [localErrors, serverErrors],
  );

  const passengerErrorsByIndex = useMemo(() => {
    const grouped: Record<number, Record<string, string>> = {};
    for (const [key, message] of Object.entries(mergedErrors)) {
      const match = key.match(/^passengers\[(\d+)\]\.(.+)$/);
      if (match) {
        const index = Number(match[1]);
        grouped[index] = { ...(grouped[index] ?? {}), [match[2]]: message };
      }
    }
    return grouped;
  }, [mergedErrors]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setServerErrors({});

    const journeyValidation = validateJourney(journey, predictionAt ?? '');
    const passengerValidation = validatePassengers(toPassengerInputs(rows));
    const merged: Record<string, string> = {
      ...journeyValidation.errors,
      ...passengerValidation.errors,
    };

    if (!journeyValidation.isValid || !passengerValidation.isValid || !predictionAt) {
      setLocalErrors(merged);
      return;
    }

    setLocalErrors({});

    const request: PredictionRequest = {
      journey: {
        ...journey,
        train_number: journey.train_number.trim(),
        boarding_station: journey.boarding_station.trim().toUpperCase(),
        destination_station: journey.destination_station.trim().toUpperCase(),
      },
      prediction_at: predictionAt,
      target,
      passengers: toPassengerInputs(rows),
    };

    await submit(request);
  };

  const handleReset = () => {
    reset();
    setLocalErrors({});
    setServerErrors({});
    resetRows();
  };

  /**
   * A 422 carries dotted server field paths. Translating them to form keys marks
   * the input the user has to fix instead of showing one undifferentiated banner.
   */
  const handleDismissFailure = () => {
    reset();
    setServerErrors({});
  };

  React.useEffect(() => {
    if (failure?.kind === 'validation') {
      const mapped: Record<string, string> = {};
      for (const [field, message] of Object.entries(failure.fieldErrors)) {
        const local = serverFieldToLocalKey(field);
        if (local) mapped[local] = message;
      }
      setServerErrors(mapped);
    } else {
      setServerErrors({});
    }
  }, [failure]);

  const statusMessage =
    state === 'loading'
      ? 'Requesting an estimate from the backend…'
      : state === 'error'
        ? 'The request did not succeed.'
        : state === 'success' && result
          ? `Response received: ${result.evidence_coverage} evidence for ${result.passenger_count} passenger(s).`
          : '';

  return (
    <div className="space-y-8">
      <div className="border-b border-gray-200 pb-6">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
          Railway confirmation likelihood
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-gray-600">
          Estimates outcomes for Indian Railways waitlist and RAC tickets at final
          chart preparation, from approved local data only. Where the evidence does
          not support an estimate, this page says so instead of showing a number.
        </p>
      </div>

      <p aria-live="polite" role="status" className="sr-only">
        {statusMessage}
      </p>

      {failure && (
        <ErrorBanner
          message={failure.message}
          code={failure.code}
          requestId={failure.requestId}
          onDismiss={handleDismissFailure}
        />
      )}

      {Object.keys(localErrors).length > 0 && state !== 'loading' && (
        <div
          role="alert"
          className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800"
        >
          <p className="font-semibold">Fix these before sending:</p>
          <ul className="mt-1 list-inside list-disc text-xs">
            {Object.entries(localErrors).map(([key, message]) => (
              <li key={key}>{message}</li>
            ))}
          </ul>
        </div>
      )}

      {state === 'success' && result ? (
        <PredictionResult result={result} onReset={handleReset} />
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6" noValidate>
          <div className="rounded-lg border border-blue-100 bg-blue-50/60 px-4 py-2 text-xs text-blue-900">
            Example journey filled in. Replace it with your booking — nothing here is
            looked up for you.
          </div>

          <JourneyForm
            value={journey}
            predictionLocalValue={predictionLocal}
            target={target}
            onChange={(updates) => setJourney((prev) => ({ ...prev, ...updates }))}
            onPredictionTimeChange={setPredictionLocal}
            onTargetChange={setTarget}
            errors={mergedErrors}
          />

          <PassengerList
            rows={rows}
            onAdd={addRow}
            onRemove={removeRow}
            onChange={updateRow}
            limitReached={limitReached}
            errors={passengerErrorsByIndex}
          />

          <div className="flex flex-col items-start justify-between gap-3 pt-2 sm:flex-row sm:items-center">
            <span className="text-xs text-gray-500">
              {isLoopbackApi() ? (
                <>
                  Requests go to {configuredApiUrl()} on this machine only. Nothing is
                  sent to a third-party service.
                </>
              ) : (
                <>
                  Requests are sent to the configured backend at{' '}
                  {configuredApiUrl()}, which is not a loopback address. The journey
                  and statuses you enter leave this device.
                </>
              )}
            </span>
            <button
              type="submit"
              disabled={state === 'loading' || rows.length > MAX_PASSENGERS}
              className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-blue-400"
            >
              {state === 'loading' ? (
                <>
                  <LoadingSpinner size="sm" />
                  Requesting estimate…
                </>
              ) : (
                'Request estimate'
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
