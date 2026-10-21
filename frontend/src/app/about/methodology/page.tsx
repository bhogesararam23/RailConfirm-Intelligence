import React from 'react';

export default function MethodologyPage() {
  return (
    <div className="max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-900 sm:text-3xl">
          Prediction Methodology & Standards
        </h1>
        <p className="mt-2 text-sm text-gray-600">
          How RailConfirm Intelligence evaluates reservation outcomes and why we report evidence limitations honestly.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">1. Target Moment & Outcome Definition</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          Our primary prediction target is the passenger&apos;s status at <strong>final chart preparation</strong> (typically 4 hours before scheduled departure). We do not mix final-chart outcomes with post-chart outcomes or train departure status without separate evaluation.
        </p>
        <div className="rounded-md border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700 space-y-1">
          <p><strong>CNF:</strong> Confirmed reservation / full berth accommodation.</p>
          <p><strong>RAC:</strong> Reservation Against Cancellation (authorized to travel, shared berth).</p>
          <p><strong>WL:</strong> Waitlisted reservation (unconfirmed at charting).</p>
          <p><strong>CANCELLED:</strong> Explicitly cancelled booking.</p>
          <p><strong>OTHER / CENSORED:</strong> Non-standard outcomes or unobserved terminal states.</p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">2. Distinction Between Observation and Prediction</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          A current ticket status of GNWL/5 is an <em>observation</em> of queue state at a specific time. A 75% chance of CNF is a <em>model estimate</em> of future movement by final chart. RailConfirm strictly separates these two concepts in the interface and never substitutes one for another.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">3. Group Joint Outcomes</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          Passengers on a single ticket share route, class, quota, and allocation constraints. Casual multiplication of individual marginal probabilities assumes statistical independence, which can severely distort group success estimates. Our group estimates explicitly declare their underlying assumptions and baseline methodology.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-gray-900">4. Current Build Status (Local-First)</h2>
        <p className="text-sm leading-relaxed text-gray-700">
          Under ADR-0007, the current build operates in a local-first environment without live IRCTC connections. When no approved historical model artifact is loaded, the engine abstains rather than inventing speculative percentage numbers.
        </p>
      </section>
    </div>
  );
}
