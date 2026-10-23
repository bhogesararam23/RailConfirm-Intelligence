'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ApiFailure, deleteStoredPrediction, fetchStoredPrediction } from '@/lib/api';
import type { PredictionResponse } from '@/lib/types';
import { PredictionResult } from './PredictionResult';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

type LoadState = 'loading' | 'found' | 'missing' | 'deleted' | 'error';

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
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState('loading');
    setReport(null);
    setFailure(null);
    setConfirmingDelete(false);
    setDeleteMessage(null);
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

  async function removeReport() {
    setRemoving(true);
    setDeleteMessage(null);
    try {
      await deleteStoredPrediction(predictionId);
      setState('deleted');
    } catch (error) {
      // Keep showing the report: a delete that did not happen must not look like one.
      setDeleteMessage(
        error instanceof ApiFailure
          ? `Not deleted: ${error.message}`
          : 'Not deleted: the backend did not answer.',
      );
      setConfirmingDelete(false);
    } finally {
      setRemoving(false);
    }
  }

  if (state === 'loading') {
    return <LoadingSpinner label={`Looking up report ${predictionId}…`} />;
  }

  if (state === 'deleted') {
    return (
      <div
        role="status"
        className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-700 shadow-sm"
      >
        <h1 className="text-lg font-semibold text-gray-900">Report deleted</h1>
        <p className="mt-2">
          This copy has been removed from the server’s history. The page you were on may still
          show it — that is your browser’s memory, not stored data.
        </p>
        <div className="mt-4 flex gap-3">
          <Link
            href="/history"
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
          >
            See what is still kept
          </Link>
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
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          {confirmingDelete ? (
            <div className="flex flex-wrap items-center gap-3">
              <span role="status" aria-live="polite" className="text-sm text-gray-800">
                Delete this stored report? Nothing else will be removed, and this cannot be
                undone.
              </span>
              <button
                type="button"
                onClick={() => void removeReport()}
                disabled={removing}
                className="rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                {removing ? 'Removing…' : 'Confirm delete'}
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Keep it
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => setConfirmingDelete(true)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Delete this report
              </button>
              {deleteMessage && (
                <span role="status" aria-live="polite" className="text-xs text-red-700">
                  {deleteMessage}
                </span>
              )}
            </div>
          )}
        </div>
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
