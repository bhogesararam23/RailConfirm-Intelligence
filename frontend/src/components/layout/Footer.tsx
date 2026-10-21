import React from 'react';

export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-gray-50 py-8 text-center text-xs text-gray-500">
      <div className="mx-auto max-w-5xl px-4">
        <p className="mb-2 font-medium text-gray-700">
          Independent Research System &middot; Not Affiliated with IRCTC or Indian Railways
        </p>
        <p className="max-w-3xl mx-auto leading-relaxed">
          RailConfirm Intelligence provides research-backed reservation outcome estimates. Predictions are probabilistic and do not guarantee confirmation. Operates in local-first mode without third-party live APIs (ADR-0007).
        </p>
      </div>
    </footer>
  );
}
