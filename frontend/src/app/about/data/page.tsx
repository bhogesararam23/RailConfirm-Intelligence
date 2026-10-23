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
            <strong>Where your input goes:</strong> this build makes no third-party
            calls — no live PNR lookup, no external news or weather feed, and no hosted
            inference (ADR-0007). The journey and statuses you enter are sent to the
            configured backend, and nowhere else. With the default local configuration
            that backend is on your own machine; if <code>NEXT_PUBLIC_API_URL</code> is
            pointed at a remote server, your input leaves this device, and the predictor
            page shows the address it is sending to.
          </li>
          <li>
            <strong>Nothing is stored unless you ask twice:</strong> a report is kept only
            when the backend has history enabled <em>and</em> the request ticks &ldquo;keep
            this report&rdquo;. Both default to off, so the ordinary case still retains
            nothing. When a report is kept it goes into one local file on the machine
            running the backend, stays inside its retention window (30 days by default, at
            least 1), and then stops being retrievable. Passenger names are absent from the
            data model, and a payload carrying a name field or a PNR-shaped value is
            refused at the write rather than stored (ADR-0005, ADR-0012). The response says
            whether it was actually kept — the request alone does not.
          </li>
          <li>
            <strong>Zero secrets in Git:</strong> no API tokens, personal records or
            unapproved data dumps are committed to this repository.
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Dataset Intake Checklist</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          A data file found online is not an approved training dataset. Every candidate
          has to satisfy the documented intake process, and the licence and privacy
          decision is made by a named person — the validation tooling explicitly refuses
          to record approval itself.
        </p>
        <div className="space-y-1 rounded-md border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700">
          <p>&bull; Documented source publisher, licence and permitted research/commercial use.</p>
          <p>&bull; Clear verification of how final-chart outcome labels were observed.</p>
          <p>&bull; Absence of raw PNRs and personal passenger details.</p>
          <p>&bull; SHA-256 checksum with a deterministic, reviewable manifest.</p>
          <p>&bull; Temporal integrity: no future outcome leaking into prediction features.</p>
          <p>&bull; A recorded decision: candidate, restricted, quarantined, approved or rejected.</p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">Current dataset status</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          <strong>No dataset has been approved for training or evaluation yet.</strong>{' '}
          The intake pipeline exists — loader, validator, manifest generation and
          verification — but nothing has passed review. The estimates this product can
          produce are therefore abstentions, and the synthetic fixtures in the test
          suite exist to check the software, never to demonstrate real-world accuracy.
        </p>
      </section>
    </div>
  );
}
