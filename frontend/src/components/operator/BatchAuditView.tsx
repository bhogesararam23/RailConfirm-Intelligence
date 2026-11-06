import React from 'react';
import type { BatchInspection } from '@/lib/types';

interface BatchAuditViewProps {
  inspection: BatchInspection;
}

export function BatchAuditView({ inspection }: BatchAuditViewProps) {
  const { summary, pii_scan, audit_report } = inspection;

  return (
    <div className="space-y-6">
      {/* Batch Metadata Card */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <h3 className="text-base font-semibold text-gray-900">Batch Metadata & Provenance</h3>
        <dl className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
          <div>
            <dt className="text-gray-500">Batch ID</dt>
            <dd className="font-mono font-medium text-gray-900">{summary.batch_id}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Schema Version</dt>
            <dd className="font-medium text-gray-900">v{summary.schema_version}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Created At</dt>
            <dd className="font-medium text-gray-900">{summary.created_at}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Canonical SHA-256</dt>
            <dd className="font-mono text-xs text-gray-700 truncate" title={summary.canonical_sha256}>
              {summary.canonical_sha256}
            </dd>
          </div>
        </dl>
      </div>

      {/* PII Scan & Governance Audit Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* PII Scanner Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Automated PII / Identifier Scan</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                pii_scan.passed
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-rose-100 text-rose-800'
              }`}
            >
              {pii_scan.passed ? 'CLEAN (0 findings)' : `FLAGGED (${pii_scan.findings_count})`}
            </span>
          </div>

          <p className="mt-2 text-sm text-gray-600">
            Automated regex pattern scanner verifying that raw 10-digit PNRs, email addresses,
            phone numbers, or personal passenger names are absent from all text fields.
          </p>

          {pii_scan.findings.length > 0 ? (
            <div className="mt-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-rose-700">Findings:</p>
              <ul className="rounded border border-rose-200 bg-rose-50 p-3 text-xs font-mono text-rose-900 space-y-1">
                {pii_scan.findings.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="mt-4 rounded border border-emerald-200 bg-emerald-50/50 p-3 text-xs text-emerald-800">
              No personal data patterns or raw identifiers detected in notes or records.
            </div>
          )}
        </div>

        {/* Scientific Audit Card */}
        <div className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Governance & Scientific Thresholds</h3>
            <span
              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                audit_report.is_technically_eligible
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-gray-100 text-gray-700'
              }`}
            >
              {audit_report.is_technically_eligible ? 'Eligible Format' : 'Format Disqualified'}
            </span>
          </div>

          <p className="mt-2 text-sm text-gray-600">
            Validates structural integrity, chronological consistency, and observational threshold coverage.
          </p>

          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-gray-500">Unique Trains</dt>
              <dd className="font-semibold text-gray-900">{audit_report.unique_trains.length} trains</dd>
            </div>
            <div>
              <dt className="text-gray-500">Unique Journey Dates</dt>
              <dd className="font-semibold text-gray-900">{audit_report.unique_journey_dates.length} dates</dd>
            </div>
            <div>
              <dt className="text-gray-500">Scientifically Adequate</dt>
              <dd className="font-medium text-gray-900">
                {audit_report.is_scientifically_adequate ? 'Yes' : 'No (Synthetic Sample)'}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Training Approved</dt>
              <dd className="font-medium text-rose-700">
                {audit_report.is_model_training_approved ? 'Yes' : 'No (Requires Real Pilot)'}
              </dd>
            </div>
          </dl>

          {audit_report.structural_errors.length > 0 && (
            <div className="mt-4 rounded border border-rose-200 bg-rose-50 p-3 text-xs text-rose-900">
              <p className="font-bold">Structural Errors:</p>
              <ul className="list-disc pl-4 mt-1 space-y-0.5">
                {audit_report.structural_errors.map((err, i) => (
                  <li key={i}>{err}</li>
                ))}
              </ul>
            </div>
          )}

          {audit_report.quality_warnings.length > 0 && (
            <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <p className="font-bold">Quality Warnings:</p>
              <ul className="list-disc pl-4 mt-1 space-y-0.5">
                {audit_report.quality_warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

