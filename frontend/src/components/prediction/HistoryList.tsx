'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ApiFailure, deleteStoredPrediction, fetchStoredReports } from '@/lib/api';
import type { StoredReportsResponse } from '@/lib/types';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

type LoadState = 'loading' | 'listed' | 'disabled' | 'error';

/**
 * The reports this server kept, and the way to stop keeping one.
 *
 * Two decisions shape this list. It shows ids, clocks and provenance only, because the
 * backend deliberately returns nothing else — a history index is where ticket detail
 * would leak if it carried the reports themselves. And deletion needs a second click:
 * removing the last copy of an estimate cannot be undone, so a single destructive button
 * in a list is a mistake waiting for a stray click.
 */
export function HistoryList() {
  const [state, setState] = useState<LoadState>('loading');
  const [data, setData] = useState<StoredReportsResponse | null>(null);
  const [failure, setFailure] = useState<ApiFailure | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [removed, setRemoved] = useState<string[]>([]);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState('loading');
    setData(null);
    setFailure(null);
    setConfirming(null);
    setRemoved([]);
    setDeleteMessage(null);
    try {
      const listed = await fetchStoredReports();
      setData(listed);
      setState('listed');
    } catch (error) {
      if (error instanceof ApiFailure) {
        setFailure(error);
        setState(error.code === 'history_disabled' ? 'disabled' : 'error');
        return;
      }
      setFailure(null);
      setState('error');
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function remove(predictionId: string) {
    setRemoving(predictionId);
    setDeleteMessage(null);
    try {
      await deleteStoredPrediction(predictionId);
      setRemoved((previous) => [...previous, predictionId]);
      setData((previous) =>
        previous
          ? {
              ...previous,
              reports: previous.reports.filter((report) => report.prediction_id !== predictionId),
              count: previous.count - 1,
            }
          : previous,
      );
      setDeleteMessage('Removed. The report is gone from this server’s history now.');
    } catch (error) {
      // The row stays listed: a refused delete must not be shown as a success, and the
      // backend answers the same way for "absent" and "already gone" so nothing here can
      // claim to know which happened.
      setDeleteMessage(
        error instanceof ApiFailure
          ? `Not deleted: ${error.message}`
          : 'Not deleted: the backend did not answer.',
      );
    } finally {
      setConfirming(null);
      setRemoving(null);
    }
  }

  if (state === 'loading') {
    return <LoadingSpinner label="Looking for kept reports…" />;
  }

  if (state === 'disabled') {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-700 shadow-sm">
        <h2 className="text-base font-semibold text-gray-900">This server keeps no history</h2>
        <p className="mt-2">
          Reports are stored only when the operator enables prediction history and the
          request asks to be kept, and this server has the first half switched off. Nothing
          here was deleted, because nothing was ever saved.
        </p>
        <Link
          href="/"
          className="mt-4 inline-block rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Start an estimate
        </Link>
      </div>
    );
  }

  if (state === 'error') {
    return (
      <div
        role="alert"
        className="rounded-lg border border-red-200 bg-red-50 p-6 text-sm text-red-800 shadow-sm"
      >
        <h2 className="text-base font-semibold">The history could not be read</h2>
        <p className="mt-2">{failure?.message ?? 'The backend did not answer as expected.'}</p>
        {failure?.requestId && (
          <p className="mt-2 text-xs text-red-700">Request id: {failure.requestId}</p>
        )}
        <button
          type="button"
          onClick={() => void load()}
          className="mt-4 rounded-md border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-800 hover:bg-red-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Try again
        </button>
      </div>
    );
  }

  const reports = data?.reports ?? [];
  // Built as one string so the count sentence is a single text node a reader — and a test —
  // can match, rather than three interpolated fragments.
  const summary = `${reports.length} kept report${reports.length === 1 ? '' : 's'} on this server.`;
  const removedNote =
    removed.length > 0
      ? `${removed.length} report${removed.length === 1 ? '' : 's'} removed in this session.`
      : null;

  if (reports.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-700 shadow-sm">
        <h2 className="text-base font-semibold text-gray-900">Nothing is being kept</h2>
        <p className="mt-2">
          This server allows history, but no report has asked to be kept yet — or every copy
          has passed its retention window, which is what the window is for.
        </p>
        {removedNote && <p className="mt-2 text-xs text-gray-600">{removedNote}</p>}
        <Link
          href="/"
          className="mt-4 inline-block rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          Start an estimate
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-gray-600">
        <span>{summary}</span> This list shows only the internal id and the clocks: no journey,
        no statuses and no probabilities leave the report itself. Each copy stops being
        retrievable after {data?.retention_days} day(s) unless you remove it here.
      </p>

      {deleteMessage && (
        <p
          role="status"
          aria-live="polite"
          className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-700"
        >
          {deleteMessage}
        </p>
      )}

      <ul className="divide-y divide-gray-100 overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        {reports.map((report) => (
          <li key={report.prediction_id} className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <Link
                href={`/prediction/${report.prediction_id}`}
                className="truncate text-sm font-medium text-blue-700 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
              >
                Report {report.prediction_id.slice(0, 8)}…
              </Link>
              <p className="mt-1 text-xs text-gray-600">
                target {report.target} · model {report.model_version}
              </p>
              <p className="text-xs text-gray-500">
                kept {report.recorded_at} · retrievable until {report.retention_expires_at}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {confirming === report.prediction_id ? (
                <>
                  <button
                    type="button"
                    onClick={() => void remove(report.prediction_id)}
                    disabled={removing === report.prediction_id}
                    className="rounded-md bg-red-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
                    {removing === report.prediction_id ? 'Removing…' : 'Confirm delete'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirming(null)}
                    className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
                    Keep it
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setDeleteMessage(null);
                    setConfirming(report.prediction_id);
                  }}
                  className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-800 hover:bg-gray-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                >
                  Delete report
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
