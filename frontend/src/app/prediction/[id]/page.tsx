import React from 'react';
import { StoredPredictionReport } from '@/components/prediction/StoredPredictionReport';

/**
 * `/prediction/[id]` — a reopened report.
 *
 * The path carries the internal id the backend returned, never a PNR or passenger
 * detail, so a bookmark is safe to keep on the device it was made on.
 */
export default function PredictionReportPage({ params }: { params: { id: string } }) {
  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <StoredPredictionReport predictionId={params.id} />
    </main>
  );
}
