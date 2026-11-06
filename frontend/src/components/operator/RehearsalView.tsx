import React, { useState } from 'react';
import type { RehearsalReportData } from '@/lib/types';

interface RehearsalViewProps {
  report: RehearsalReportData | null;
  summaryText: string | null;
  onRunRehearsal: () => Promise<void>;
  isRunning: boolean;
}

export function RehearsalView({
  report,
  summaryText,
  onRunRehearsal,
  isRunning,
}: RehearsalViewProps) {
  const [expandedGates, setExpandedGates] = useState<Record<string, boolean>>({});
  const [showRawSummary, setShowRawSummary] = useState<boolean>(false);

  const toggleGate = (gateId: string) => {
    setExpandedGates((prev) => ({
      ...prev,
      [gateId]: !prev[gateId],
    }));
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
        return <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">PASS</span>;
      case 'warn':
        return <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">WARN</span>;
      default:
        return <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">FAIL</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Trigger */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
        <div>
          <h3 className="text-base font-semibold text-gray-900">
            Prospective Lifecycle Synthetic Rehearsal
          </h3>
          <p className="mt-1 text-xs text-gray-500">
            Executes all 15 gates of the offline prospective lifecycle (batch intake, PII scan, audit, review, withdrawal, export, lineage, stale detection, reconciliation, quarantine, filesystem, and abstention).
          </p>
        </div>
        <button
          type="button"
          onClick={onRunRehearsal}
          disabled={isRunning}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        >
          {isRunning ? 'Running Rehearsal…' : 'Execute 15-Gate Rehearsal'}
        </button>
      </div>

      {!report ? (
        <div className="rounded-lg border border-gray-200 bg-white p-12 text-center text-sm text-gray-500">
          <p className="text-base font-medium text-gray-700">No Rehearsal Run Recorded</p>
          <p className="mt-1">
            Click &apos;Execute 15-Gate Rehearsal&apos; to run an end-to-end dry run on local synthetic data.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Readiness Statement Banner */}
          <div
            className={`rounded-lg border p-5 shadow-sm ${
              report.software_rehearsal_passed
                ? 'border-emerald-200 bg-emerald-50/70 text-emerald-950'
                : 'border-rose-200 bg-rose-50 text-rose-950'
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-gray-200/50 pb-3">
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-gray-600">
                  Run ID: {report.run_id} ({report.run_timestamp})
                </span>
                <h4 className="text-lg font-bold">
                  {report.software_rehearsal_passed
                    ? 'SOFTWARE REHEARSAL PASSED'
                    : 'SOFTWARE REHEARSAL FAILED'}
                </h4>
              </div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-rose-200/80 px-2.5 py-1 text-xs font-bold text-rose-900 uppercase">
                  Real-World Pilot Authorized: NO
                </span>
                {getStatusBadge(report.overall_status)}
              </div>
            </div>

            <p className="mt-3 text-xs leading-relaxed font-medium">
              {report.readiness_statement}
            </p>
          </div>

          {/* Gates Accordion List */}
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
            <div className="border-b border-gray-200 bg-gray-50 px-4 py-3 flex items-center justify-between">
              <h4 className="text-sm font-semibold text-gray-900">
                Gate Evaluation Results ({report.gates.length} gates)
              </h4>
              <button
                type="button"
                onClick={() => setShowRawSummary(!showRawSummary)}
                className="text-xs text-blue-600 hover:text-blue-800 underline"
              >
                {showRawSummary ? 'Hide plain text summary' : 'View plain text summary'}
              </button>
            </div>

            {showRawSummary && summaryText && (
              <pre className="max-h-72 overflow-auto bg-gray-900 p-4 font-mono text-xs text-gray-100">
                {summaryText}
              </pre>
            )}

            <div className="divide-y divide-gray-200">
              {report.gates.map((g, idx) => {
                const isExpanded = !!expandedGates[g.gate_id];
                return (
                  <div key={g.gate_id} className="p-4">
                    <div
                      className="flex cursor-pointer items-center justify-between gap-2"
                      onClick={() => toggleGate(g.gate_id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') toggleGate(g.gate_id);
                      }}
                      aria-expanded={isExpanded}
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-xs text-gray-400">
                          {String(idx + 1).padStart(2, '0')}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-gray-900">{g.title}</p>
                          <p className="font-mono text-[11px] text-gray-500">{g.gate_id}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {getStatusBadge(
                          g.failures.length > 0
                            ? 'fail'
                            : g.warnings.length > 0
                            ? 'warn'
                            : 'pass'
                        )}
                        <span className="text-xs text-gray-400">{isExpanded ? '▲' : '▼'}</span>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 space-y-2 pl-8 text-xs">
                        {g.evidence.length > 0 && (
                          <div className="rounded bg-gray-50 p-2.5 border border-gray-100">
                            <p className="font-semibold text-gray-700">Observed Evidence:</p>
                            <ul className="list-disc pl-4 mt-1 space-y-0.5 text-gray-600">
                              {g.evidence.map((item, i) => (
                                <li key={i}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {g.failures.length > 0 && (
                          <div className="rounded bg-rose-50 p-2.5 border border-rose-200 text-rose-900">
                            <p className="font-semibold">Failures:</p>
                            <ul className="list-disc pl-4 mt-1 space-y-0.5">
                              {g.failures.map((item, i) => (
                                <li key={i}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {g.warnings.length > 0 && (
                          <div className="rounded bg-amber-50 p-2.5 border border-amber-200 text-amber-900">
                            <p className="font-semibold">Warnings:</p>
                            <ul className="list-disc pl-4 mt-1 space-y-0.5">
                              {g.warnings.map((item, i) => (
                                <li key={i}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {g.human_actions.length > 0 && (
                          <div className="rounded bg-blue-50 p-2.5 border border-blue-200 text-blue-900">
                            <p className="font-semibold">Required Human Actions:</p>
                            <ul className="list-disc pl-4 mt-1 space-y-0.5">
                              {g.human_actions.map((item, i) => (
                                <li key={i}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
