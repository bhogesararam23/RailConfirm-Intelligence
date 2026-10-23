'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiFailure, fetchStoredPrediction } from '@/lib/api';
import type { PredictionResponse } from '@/lib/types';
import { PredictionResult } from './PredictionResult';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

type LoadState = 'loading' | 'found' | 'missing' | 'error';

interface StoredPredictionReportProps {
  predictionId: string;
}

/**
 * A reopened report, or the reason there is nothing to show.
 *
 * "Not found" is not one message here. The id was never stored, it aged out, and this
 * server keeps no history at all are three different facts, and telling the user the
 * wrong one would be a lie about the system they are using.
 */
export function StoredPredictionReport({ predictionId }: StoredPredictionReportProps) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>('loading');
  const [report, setReport] = useState<PredictionResponse | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);

  const load = useCallback(async () => {
    setState('loading');
    setReport(null);
    setFailure(null);
    try {
      const stored = await fetchStoredPrediction(predictionId);
      setReport(stored);
      setState('found');
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFailure(error);
        setState(error.status === 404 ? 'missing' : 'error');
        return;
      }
      setFailure(null);
      setState('error');
    }
  }, [predictionId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state === 'loading') {
    return <LoadingSpinner label={`Looking up report ${predictionId}…`} />;
  }

  if (state === 'found' && report) {
    return (
      <div className="space-y-4">
        <p className="rounded-lg border border-gray-200 bg-gray-50 px-4 py-2 text-xs text-gray-700">
          This is the report as it was served, including the model version that produced
          it. Estimates are not recomputed on open.
          {report.retention_expires_at && (
            <> This copy stops being retrievable after {report.retention_expires_at}.</>
          )}
        </p>
        <PredictionResult result={report} onReset={() => router.push('/')} />
      </div>
    );
  }

  const message =
    state === 'missing'
      ? failure?.code === 'history_disabled'
        ? 'This server keeps no prediction history, so no report can be reopened here.'
        : 'No stored report has this id. It may never have been stored, or its retention window has closed.'
      : failure?.message ??
        'The stored report could not be read. The backend may not be running.';

  return (
    <div
      role="status"
      className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-700 shadow-sm"
    >
      <h1 className="text-lg font-semibold text-gray-900">Report not available</h1>
      <p className="mt-2">{message}</p>
      {failure?.requestId && (
        <p className="mt-2 text-xs text-gray-500">Request id: {failure.requestId}</p>
      )}
      <div className="mt-4 flex gap-3">
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Try again
        </button>
        <button
          type="button"
          onClick={() => router.push('/')}
          className="rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Start a new estimate
        </button>
      </div>
    </div>
  );
}
