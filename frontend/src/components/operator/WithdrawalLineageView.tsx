import React, { useState } from 'react';
import type { BatchInspection, ExportPreview, LineageInspection } from '@/lib/types';

interface WithdrawalLineageViewProps {
  inspection: BatchInspection;
  lineage: LineageInspection | null;
  exportPreview: ExportPreview | null;
  onWithdraw: (submissionId: string, reason: string, operator: string) => Promise<void>;
  onExport: () => Promise<void>;
  onReconcile: () => Promise<void>;
  onRefreshLineage: () => Promise<void>;
  isExporting: boolean;
  isReconciling: boolean;
}

export function WithdrawalLineageView({
  inspection,
  lineage,
  exportPreview,
  onWithdraw,
  onExport,
  onReconcile,
  onRefreshLineage,
  isExporting,
  isReconciling,
}: WithdrawalLineageViewProps) {
  const [withdrawSubId, setWithdrawSubId] = useState<string>('');
  const [withdrawReason, setWithdrawReason] = useState<string>('');
  const [operatorId, setOperatorId] = useState<string>('operator_lead');
  const [withdrawing, setWithdrawing] = useState<boolean>(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [withdrawSuccess, setWithdrawSuccess] = useState<string | null>(null);

  const handleWithdrawSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!withdrawSubId.trim() || !withdrawReason.trim() || !operatorId.trim()) {
      setWithdrawError('All fields (submission, reason, operator) are required.');
      return;
    }

    setWithdrawing(true);
    setWithdrawError(null);
    setWithdrawSuccess(null);
    try {
      await onWithdraw(withdrawSubId.trim(), withdrawReason.trim(), operatorId.trim());
      setWithdrawSuccess(`Submission ${withdrawSubId.trim()} withdrawn successfully.`);
      setWithdrawSubId('');
      setWithdrawReason('');
    } catch (err: unknown) {
      setWithdrawError(err instanceof Error ? err.message : 'Withdrawal recording failed.');
    } finally {
      setWithdrawing(false);
    }
  };

  const getLineageBadge = (status: string | undefined) => {
    switch (status) {
      case 'verified_in_sync':
        return <span className="rounded bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">Verified In Sync</span>;
      case 'stale_withdrawn_records_present':
        return <span className="rounded bg-rose-100 px-2.5 py-0.5 text-xs font-semibold text-rose-800">STALE: Withdrawn Records Present</span>;
      case 'stale_source_modified':
        return <span className="rounded bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">STALE: Source Modified</span>;
      default:
        return <span className="rounded bg-gray-100 px-2.5 py-0.5 text-xs font-semibold text-gray-800">No Export Found</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Participant Withdrawal Form */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-gray-900">Record Participant Consent Withdrawal</h3>
        <p className="mt-1 text-xs text-gray-500">
          Under DPDP privacy principles, a participant may withdraw consent at any time. Withdrawing immediately
          disqualifies the submission from future exports and marks existing exports as stale until reconciled.
        </p>

        {withdrawSuccess && (
          <div role="status" className="mt-3 rounded border border-emerald-300 bg-emerald-50 p-3 text-xs text-emerald-800">
            {withdrawSuccess}
          </div>
        )}
        {withdrawError && (
          <div role="alert" className="mt-3 rounded border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
            {withdrawError}
          </div>
        )}

        <form onSubmit={handleWithdrawSubmit} className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="withdraw-sub" className="block text-xs font-medium text-gray-700">
              Submission ID:
            </label>
            <select
              id="withdraw-sub"
              value={withdrawSubId}
              onChange={(e) => setWithdrawSubId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="">Select submission…</option>
              {inspection.submissions
                .filter((s) => s.review_status !== 'withdrawn')
                .map((s) => (
                  <option key={s.submission_id} value={s.submission_id}>
                    {s.submission_id} ({s.review_status})
                  </option>
                ))}
            </select>
          </div>

          <div>
            <label htmlFor="operator-id" className="block text-xs font-medium text-gray-700">
              Operator Identifier:
            </label>
            <input
              type="text"
              id="operator-id"
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div>
            <label htmlFor="withdraw-reason" className="block text-xs font-medium text-gray-700">
              Withdrawal Reason:
            </label>
            <input
              type="text"
              id="withdraw-reason"
              value={withdrawReason}
              onChange={(e) => setWithdrawReason(e.target.value)}
              placeholder="e.g. Participant requested withdrawal"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <div className="sm:col-span-3 flex justify-end">
            <button
              type="submit"
              disabled={withdrawing}
              className="rounded-md bg-rose-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-rose-700 focus:outline-none focus:ring-2 focus:ring-rose-500 disabled:opacity-50"
            >
              {withdrawing ? 'Recording withdrawal…' : 'Record Withdrawal'}
            </button>
          </div>
        </form>
      </div>

      {/* Withdrawal Audit Trail */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-gray-900">
          Withdrawal Audit Trail ({inspection.withdrawal_log.length})
        </h3>
        {inspection.withdrawal_log.length === 0 ? (
          <p className="mt-2 text-xs italic text-gray-400">No withdrawals recorded for this batch.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-xs">
              <thead className="bg-gray-50 uppercase tracking-wider text-gray-500">
                <tr>
                  <th scope="col" className="px-3 py-2">Timestamp</th>
                  <th scope="col" className="px-3 py-2">Submission</th>
                  <th scope="col" className="px-3 py-2">Pseudonym Group</th>
                  <th scope="col" className="px-3 py-2">Prior Status</th>
                  <th scope="col" className="px-3 py-2">Operator</th>
                  <th scope="col" className="px-3 py-2">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {inspection.withdrawal_log.map((w, i) => (
                  <tr key={i}>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-500">{w.withdrawn_at}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono font-semibold text-gray-800">{w.submission_id}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono text-gray-600">{w.pseudonym_group_id}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-600">{w.prior_review_status}</td>
                    <td className="whitespace-nowrap px-3 py-2 text-gray-800">{w.operator}</td>
                    <td className="px-3 py-2 text-gray-700">{w.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Export & Lineage Controls */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Export Preview Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Approved Dataset Export</h3>
            <button
              type="button"
              onClick={onExport}
              disabled={isExporting}
              className="rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:opacity-50"
            >
              {isExporting ? 'Exporting…' : 'Execute Export'}
            </button>
          </div>

          <p className="mt-2 text-xs text-gray-600">
            Exports only approved submissions into the standardized longitudinal research format (v2.0.0).
            Withdrawn, rejected, and unreviewed records are strictly excluded.
          </p>

          {exportPreview && (
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm rounded bg-gray-50 p-3 border border-gray-100">
              <div>
                <dt className="text-xs text-gray-500">Approved for Export</dt>
                <dd className="font-semibold text-emerald-800">{exportPreview.approved_count} submissions</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Excluded (Withdrawn/Pending)</dt>
                <dd className="font-semibold text-gray-700">{exportPreview.excluded_count} submissions</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Booking Groups</dt>
                <dd className="font-medium text-gray-900">{exportPreview.booking_groups_count}</dd>
              </div>
              <div>
                <dt className="text-xs text-gray-500">Passenger Observations</dt>
                <dd className="font-medium text-gray-900">{exportPreview.passenger_reservations_count}</dd>
              </div>
            </dl>
          )}
        </div>

        {/* Lineage Verification & Reconcile Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Lineage & Reconciliation</h3>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onRefreshLineage}
                className="rounded border border-gray-300 bg-white px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-50 focus:outline-none"
              >
                Verify Lineage
              </button>
              {lineage && !lineage.is_synced && (
                <button
                  type="button"
                  onClick={onReconcile}
                  disabled={isReconciling}
                  className="rounded bg-rose-600 px-3 py-1 text-xs font-semibold text-white shadow-sm hover:bg-rose-700 focus:outline-none disabled:opacity-50"
                >
                  {isReconciling ? 'Reconciling…' : 'Reconcile Now'}
                </button>
              )}
            </div>
          </div>

          <div className="mt-3">
            <p className="text-xs text-gray-500">Lineage Status:</p>
            <div className="mt-1">{getLineageBadge(lineage?.status)}</div>
          </div>

          {lineage && (
            <div className="mt-4 space-y-2 text-xs">
              <div className="flex justify-between border-b border-gray-100 pb-1">
                <span className="text-gray-500">Recorded Batch SHA:</span>
                <span className="font-mono text-gray-800 truncate max-w-[200px]" title={lineage.recorded_source_sha256}>
                  {lineage.recorded_source_sha256 || 'None'}
                </span>
              </div>
              <div className="flex justify-between border-b border-gray-100 pb-1">
                <span className="text-gray-500">Current Batch SHA:</span>
                <span className="font-mono text-gray-800 truncate max-w-[200px]" title={lineage.current_source_sha256}>
                  {lineage.current_source_sha256}
                </span>
              </div>
              {lineage.withdrawn_groups_present.length > 0 && (
                <div className="rounded border border-rose-200 bg-rose-50 p-2 text-rose-900">
                  <p className="font-bold">Withdrawn Groups Still in Export:</p>
                  <p className="font-mono">{lineage.withdrawn_groups_present.join(', ')}</p>
                  <p className="mt-1 text-[11px] text-rose-800">
                    Click &apos;Reconcile Now&apos; to regenerate the export and remove these records.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
