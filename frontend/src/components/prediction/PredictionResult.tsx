'use client';

import React from 'react';
import type { PredictionResponse } from '@/lib/types';
import { PassengerOutcomeCard } from './PassengerOutcomeCard';
import { GroupOutcomeCard } from './GroupOutcomeCard';

interface PredictionResultProps {
  result: PredictionResponse;
  onReset: () => void;
}

export function PredictionResult({ result, onReset }: PredictionResultProps) {
  const isFullySupported = result.passenger_outcomes.every((p) => p.is_supported);

  return (
    <div className="space-y-6">
      {/* Top status bar */}
      <div className="flex flex-col gap-3 rounded-lg border border-gray-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-gray-900">Prediction Report</h2>
            <span
              className={`rounded px-2.5 py-0.5 text-xs font-semibold ${
                isFullySupported
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-800'
              }`}
            >
              {isFullySupported ? 'Supported Forecast' : 'Model Abstaining / Insufficient Evidence'}
            </span>
          </div>
          <p className="mt-1 text-xs text-gray-500">
            Target: <span className="font-mono text-gray-700">Final Chart Preparation</span> &middot; Model:{' '}
            <span className="font-mono text-gray-700">{result.model_version}</span>
          </p>
        </div>

        <button
          type="button"
          onClick={onReset}
          className="self-start rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50 sm:self-auto"
        >
          &larr; New Prediction
        </button>
      </div>

      {/* Per-passenger cards */}
      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">
          Passenger Outcomes ({result.passenger_outcomes.length})
        </h3>
        <div className="grid grid-cols-1 gap-4">
          {result.passenger_outcomes.map((po, idx) => (
            <PassengerOutcomeCard key={po.passenger_id || idx} index={idx} outcome={po} />
          ))}
        </div>
      </div>

      {/* Group outcome if multiple passengers */}
      {result.group_outcome && result.passenger_outcomes.length > 1 && (
        <GroupOutcomeCard
          group={result.group_outcome}
          passengerCount={result.passenger_outcomes.length}
        />
      )}

      {/* Warnings & Limitations */}
      {(result.limitations.length > 0 || result.warnings.length > 0) && (
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
            Evidence Context & Limitations
          </h4>
          {result.warnings.length > 0 && (
            <div className="mb-3 space-y-1">
              <span className="text-xs font-semibold text-amber-800">Warnings:</span>
              <ul className="list-inside list-disc text-xs text-amber-700">
                {result.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
          {result.limitations.length > 0 && (
            <ul className="list-inside list-disc space-y-1 text-xs text-gray-600">
              {result.limitations.map((lim, idx) => (
                <li key={idx}>{lim}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
