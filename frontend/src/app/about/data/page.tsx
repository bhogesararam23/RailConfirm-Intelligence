import React from 'react';

export default function DataGovernancePage() {
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
          Data Governance & Privacy Baseline
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          Our commitments to privacy, data provenance, and ethical railway research.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Privacy by Design (ADR-0005)</h2>
        <ul className="list-inside list-disc space-y-2 text-sm leading-relaxed text-gray-700">
          <li>
            <strong>No Passenger Names:</strong> Passenger names are never collected or required for prediction estimation.
          </li>
          <li>
            <strong>Internal Random IDs:</strong> Public resource identifiers use randomly generated UUIDs, never raw PNR numbers.
          </li>
          <li>
            <strong>Zero Secrets in Git:</strong> No API tokens, personal records, or unapproved data dumps are committed to this repository.
          </li>
          <li>
            <strong>No Private Data Transmission:</strong> The current build operates locally. Your manual queries stay within your own local browser and backend.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Dataset Intake Checklist</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          A candidate data file found online is not automatically approved for model training. Every dataset must satisfy our documented intake checklist:
        </p>
        <div className="rounded-md border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700 space-y-1">
          <p>&bull; Documented source publisher, license, and permitted commercial/research use.</p>
          <p>&bull; Clear verification of final outcome labels (final-chart status).</p>
          <p>&bull; Absence of raw PNRs or personal passenger details.</p>
          <p>&bull; Cryptographic checksum (SHA-256) and versioned YAML manifest.</p>
          <p>&bull; Temporal integrity: zero leakage of future chart outcomes into prediction features.</p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Current Dataset Status</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          No external historical dataset is currently approved for production inference. Synthetic fixtures are maintained strictly for testing and validation of domain logic.
        </p>
      </section>
    </div>
  );
}
