import React from 'react';

export function OperatorBanner() {
  return (
    <div
      role="region"
      aria-label="Operator safety and privacy notice"
      className="mb-6 rounded-lg border-2 border-amber-300 bg-amber-50 p-4 text-amber-950 shadow-sm"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 text-xl font-bold" aria-hidden="true">
          ⚠️
        </span>
        <div className="space-y-1 text-sm">
          <p className="font-semibold text-amber-900">
            Local Operator Workbench — Offline Governance Simulation
          </p>
          <p className="text-amber-800">
            This tool operates strictly on local synthetic fixtures. Synthetic rehearsal outcomes
            do <strong>not</strong> represent real railway evidence, and software rehearsal
            success does <strong>not</strong> authorize a real-world pilot.
          </p>
          <p className="text-xs text-amber-700">
            No external APIs, IRCTC services, real participant data, or unauthorized credentials are used.
          </p>
        </div>
      </div>
    </div>
  );
}

