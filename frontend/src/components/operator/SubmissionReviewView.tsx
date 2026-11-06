'use client';

import React, { useState } from 'react';
import type { BatchInspection } from '@/lib/types';

interface SubmissionReviewViewProps {
  inspection: BatchInspection;
  onReview: (submissionId: string, action: string, reviewer: string, rationale: string) => Promise<void>;
}

export function SubmissionReviewView({ inspection, onReview }: SubmissionReviewViewProps) {
  const [selectedSubmissionId, setSelectedSubmissionId] = useState<string | null>(null);
  const [reviewAction, setReviewAction] = useState<string>('approved');
  const [reviewer, setReviewer] = useState<string>('operator_lead');
  const [rationale, setRationale] = useState<string>('');
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const selectedSub = inspection.submissions.find((s) => s.submission_id === selectedSubmissionId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedSubmissionId) return;
    if (!reviewer.trim()) {
      setFormError('Reviewer identifier is required.');
      return;
    }
    if (!rationale.trim()) {
      setFormError('Review rationale is required.');
      return;
    }

    setSubmitting(true);
    setFormError(null);
    setSuccessMsg(null);
    try {
      await onReview(selectedSubmissionId, reviewAction, reviewer.trim(), rationale.trim());
      setSuccessMsg(`Submission ${selectedSubmissionId} transitioned to ${reviewAction.toUpperCase()}.`);
      setRationale('');
      setSelectedSubmissionId(null);
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Review submission failed.');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">Approved</span>;
      case 'rejected':
        return <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">Rejected</span>;
      case 'quarantined':
        return <span className="rounded bg-purple-100 px-2 py-0.5 text-xs font-semibold text-purple-800">Quarantined</span>;
      case 'withdrawn':
        return <span className="rounded bg-gray-100 px-2 py-0.5 text-xs font-semibold text-gray-800">Withdrawn</span>;
      default:
        return <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">Pending Review</span>;
    }
  };

  return (
    <div className="space-y-6">
      {successMsg && (
        <div role="status" className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800">
          {successMsg}
        </div>
      )}

      {/* Submissions Table */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="border-b border-gray-200 bg-gray-50 px-4 py-3">
          <h3 className="text-base font-semibold text-gray-900">
            Prospective Submissions ({inspection.submissions.length})
          </h3>
          <p className="text-xs text-gray-500">
            Click &apos;Review&apos; on a submission to inspect pseudonymized group details and record an operator decision.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
            <thead className="bg-gray-50 text-xs font-medium uppercase tracking-wider text-gray-500">
              <tr>
                <th scope="col" className="px-4 py-3">Submission</th>
                <th scope="col" className="px-4 py-3">Pseudonym Group</th>
                <th scope="col" className="px-4 py-3">Train / Date</th>
                <th scope="col" className="px-4 py-3">Route / Class</th>
                <th scope="col" className="px-4 py-3">Passengers</th>
                <th scope="col" className="px-4 py-3">Status</th>
                <th scope="col" className="px-4 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {inspection.submissions.map((sub) => (
                <tr key={sub.submission_id} className="hover:bg-gray-50/75">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs font-semibold text-gray-900">
                    {sub.submission_id}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-gray-600">
                    {sub.pseudonym_group_id}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-700">
                    {sub.train_number} on {sub.journey_date}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-700">
                    {sub.boarding_station} → {sub.destination_station} ({sub.class_code}/{sub.quota_code})
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-gray-700">
                    {sub.passengers.length} passenger{sub.passengers.length > 1 ? 's' : ''}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs">
                    {getStatusBadge(sub.review_status)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-right text-xs">
                    <button
                      type="button"
                      aria-label={`Review ${sub.submission_id}`}
                      onClick={() => {
                        setSelectedSubmissionId(sub.submission_id);
                        setReviewAction(sub.review_status === 'pending_review' ? 'approved' : sub.review_status);
                        setFormError(null);
                      }}
                      className="rounded bg-gray-100 px-2.5 py-1 font-medium text-gray-700 hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Review Modal / Drawer */}
      {selectedSub && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="review-modal-title"
          className="rounded-lg border-2 border-blue-200 bg-white p-5 shadow-md"
        >
          <div className="flex items-center justify-between border-b border-gray-200 pb-3">
            <h4 id="review-modal-title" className="text-base font-bold text-gray-900">
              Review Submission: {selectedSub.submission_id}
            </h4>
            <button
              type="button"
              onClick={() => setSelectedSubmissionId(null)}
              className="text-gray-400 hover:text-gray-600 focus:outline-none"
            >
              ✕
            </button>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-3">
            <div>
              <p className="text-xs text-gray-500">Pseudonym Group</p>
              <p className="font-mono font-medium text-gray-900">{selectedSub.pseudonym_group_id}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Train / Route</p>
              <p className="font-medium text-gray-900">
                {selectedSub.train_number} ({selectedSub.boarding_station} → {selectedSub.destination_station})
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Current Review State</p>
              <div className="mt-0.5">{getStatusBadge(selectedSub.review_status)}</div>
            </div>
          </div>

          {/* Passenger details */}
          <div className="mt-4 rounded border border-gray-100 bg-gray-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-600 mb-2">
              Passenger Observations ({selectedSub.passengers.length})
            </p>
            <div className="space-y-2">
              {selectedSub.passengers.map((p) => (
                <div key={p.passenger_sequence} className="flex flex-wrap items-center justify-between text-xs text-gray-700 bg-white p-2 rounded border border-gray-200">
                  <span>Passenger {p.passenger_sequence}: <strong>{p.original_status_raw}</strong> ({p.original_status_category})</span>
                  {p.outcome ? (
                    <span className="text-gray-600">
                      Outcome: <strong>{p.outcome.outcome_status_raw}</strong> ({p.outcome.outcome_category}) via {p.outcome.verification_method}
                    </span>
                  ) : (
                    <span className="italic text-gray-400">Outcome pending</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Decision Form */}
          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            {formError && (
              <div role="alert" className="rounded border border-rose-300 bg-rose-50 p-3 text-xs text-rose-800">
                {formError}
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="review-action" className="block text-xs font-medium text-gray-700">
                  Review Action:
                </label>
                <select
                  id="review-action"
                  value={reviewAction}
                  onChange={(e) => setReviewAction(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="approved">Approved (eligible for export)</option>
                  <option value="rejected">Rejected (excluded from export)</option>
                  <option value="quarantined">Quarantined (isolated for investigation)</option>
                  <option value="flagged_for_clarification">Flagged for Clarification</option>
                </select>
              </div>

              <div>
                <label htmlFor="reviewer-id" className="block text-xs font-medium text-gray-700">
                  Reviewer Identifier:
                </label>
                <input
                  type="text"
                  id="reviewer-id"
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-1.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  placeholder="e.g. operator_alpha"
                />
              </div>
            </div>

            <div>
              <label htmlFor="review-rationale" className="block text-xs font-medium text-gray-700">
                Review Rationale (No personal data or PNRs):
              </label>
              <textarea
                id="review-rationale"
                rows={2}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="State technical justification for this decision..."
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setSelectedSubmissionId(null)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="rounded-md bg-blue-600 px-4 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {submitting ? 'Recording decision…' : 'Save Review Decision'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
