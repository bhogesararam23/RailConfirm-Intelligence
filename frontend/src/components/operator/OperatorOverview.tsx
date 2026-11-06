import React from 'react';
import type { BatchSummary, OperatorStatus } from '@/lib/types';

interface OperatorOverviewProps {
  status: OperatorStatus;
  batches: BatchSummary[];
  selectedBatchId: string | null;
  onSelectBatch: (batchId: string) => void;
  onSeedBatch: () => void;
  onRunRehearsal: () => void;
  onRefresh: () => void;
  isSeeding: boolean;
  isRehearsing: boolean;
}

export function OperatorOverview({
  status,
  batches,
  selectedBatchId,
  onSelectBatch,
  onSeedBatch,
  onRunRehearsal,
  onRefresh,
  isSeeding,
  isRehearsing,
}: OperatorOverviewProps) {
  return (
    <div className="space-y-6">
      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-gray-500">Batches</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{status.batches_count}</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-gray-500">Submissions</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">{status.total_submissions}</p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-amber-700">Pending</p>
          <p className="mt-1 text-2xl font-bold text-amber-900">{status.total_pending_review}</p>
        </div>
        <div className="rounded-lg border border-emerald-200 bg-emerald-50/50 p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-emerald-700">Approved</p>
          <p className="mt-1 text-2xl font-bold text-emerald-900">{status.total_approved}</p>
        </div>
        <div className="rounded-lg border border-rose-200 bg-rose-50/50 p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-rose-700">Withdrawn</p>
          <p className="mt-1 text-2xl font-bold text-rose-900">{status.total_withdrawn}</p>
        </div>
        <div className="rounded-lg border border-blue-200 bg-blue-50/50 p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wider text-blue-700">Rehearsal</p>
          <p className="mt-1 text-sm font-bold text-blue-900">
            {status.latest_rehearsal_passed === null
              ? 'Not Run'
              : status.latest_rehearsal_passed
              ? 'PASS (15/15)'
              : 'FAIL'}
          </p>
        </div>
      </div>

      {/* Control Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <label htmlFor="batch-select" className="text-sm font-medium text-gray-700">
            Active Batch:
          </label>
          <select
            id="batch-select"
            value={selectedBatchId ?? ''}
            onChange={(e) => onSelectBatch(e.target.value)}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {batches.length === 0 ? (
              <option value="">No batches available</option>
            ) : (
              batches.map((b) => (
                <option key={b.batch_id} value={b.batch_id}>
                  {b.batch_id} ({b.total_submissions} submissions)
                </option>
              ))
            )}
          </select>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={onSeedBatch}
            disabled={isSeeding}
            className="inline-flex items-center rounded-md bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {isSeeding ? 'Seeding fixture…' : 'Seed Synthetic Batch'}
          </button>
          <button
            type="button"
            onClick={onRunRehearsal}
            disabled={isRehearsing}
            className="inline-flex items-center rounded-md bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
          >
            {isRehearsing ? 'Rehearsing (15 gates)…' : 'Run Synthetic Rehearsal'}
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center rounded-md bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm border border-gray-300 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Refresh
          </button>
        </div>
      </div>
    </div>
  );
}

