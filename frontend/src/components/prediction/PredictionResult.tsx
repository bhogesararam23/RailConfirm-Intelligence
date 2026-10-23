'use client';

import React from 'react';
import type { PredictionResponse } from '@/lib/types';
import { PassengerOutcomeCard } from './PassengerOutcomeCard';
import { GroupOutcomeCard } from './GroupOutcomeCard';
import { formatEvidenceCoverage, formatTimestamp } from '@/lib/statusUtils';

interface PredictionResultProps {
  result: PredictionResponse;
  onReset: () => void;
}

const TARGET_LABELS: Record<string, string> = {
  final_chart_cnf: 'Confirmed berth at final chart preparation',
  final_chart_cnf_or_rac: 'CNF or RAC at final chart preparation',
};

/**
 * The full prediction report.
 *
 * Provenance is shown up front rather than hidden: target, as-of time, model and
 * feature-schema versions, registry state and evidence coverage are what let a
 * reader judge whether a number means anything. `evidence_coverage` is the precise
 * signal — a mixed group is `partial`, which is neither "supported" nor "abstaining".
 */
export function PredictionResult({ result, onReset }: PredictionResultProps) {
  const supportedCount = result.passenger_outcomes.filter((p) => p.is_supported).length;
  const coverageTone =
    result.evidence_coverage === 'sufficient'
      ? 'bg-emerald-100 text-emerald-800'
      : result.evidence_coverage === 'partial'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-gray-200 text-gray-800';

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-lg font-bold text-gray-900">Prediction report</h2>
              <span className={`rounded px-2.5 py-0.5 text-xs font-semibold ${coverageTone}`}>
                {formatEvidenceCoverage(result.evidence_coverage)}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {supportedCount} of {result.passenger_count}{' '}
              {result.passenger_count === 1 ? 'passenger has' : 'passengers have'} an
              estimate.
            </p>
          </div>
          <button
            type="button"
            onClick={onReset}
            className="self-start rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm hover:bg-gray-50"
          >
            ← New prediction
          </button>
        </div>

        <dl className="mt-4 grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
          <Row label="Target">{TARGET_LABELS[result.target] ?? result.target}</Row>
          <Row label="Predicted as of">{formatTimestamp(result.prediction_at)}</Row>
          <Row label="Model version">
            <code className="font-mono">{result.model_version}</code>
          </Row>
          <Row label="Registry state">
            <code className="font-mono">{result.registry_status}</code>
          </Row>
          <Row label="Feature schema">
            <code className="font-mono">{result.feature_schema_version}</code>
          </Row>
          <Row label="Request recorded at">{formatTimestamp(result.created_at)}</Row>
          <Row label="Prediction ID">
            <code className="break-all font-mono">{result.prediction_id}</code>
          </Row>
        </dl>
      </div>

      <div className="space-y-4">
        <h3 className="text-sm font-semibold text-gray-900">
          Passenger outcomes ({result.passenger_outcomes.length})
        </h3>
        <div className="grid grid-cols-1 gap-4">
          {result.passenger_outcomes.map((outcome, index) => (
            <PassengerOutcomeCard
              key={outcome.passenger_id || index}
              index={index}
              outcome={outcome}
            />
          ))}
        </div>
      </div>

      {result.group_outcome && (
        <GroupOutcomeCard
          group={result.group_outcome}
          passengerCount={result.passenger_count}
        />
      )}

      {(result.limitations.length > 0 || result.warnings.length > 0) && (
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Evidence context and limitations
          </h4>
          {result.warnings.length > 0 && (
            <div className="mb-3 space-y-1">
              <span className="text-xs font-semibold text-amber-800">Warnings</span>
              <ul className="list-inside list-disc text-xs text-amber-700">
                {result.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            </div>
          )}
          {result.limitations.length > 0 && (
            <ul className="list-inside list-disc space-y-1 text-xs text-gray-600">
              {result.limitations.map((limitation, index) => (
                <li key={index}>{limitation}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      <p className="text-[11px] text-gray-400">
        Outcome classes: {result.outcome_classes}
      </p>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-gray-400">{label}</dt>
      <dd className="font-medium text-gray-800">{children}</dd>
    </div>
  );
}
