import React from 'react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { HistoryList } from '@/components/prediction/HistoryList';

export const metadata: Metadata = {
  title: 'Kept reports — RailConfirm Intelligence',
  description:
    'The prediction reports this server has kept, and the way to remove one before its retention window closes.',
};

/**
 * `/history` — what this machine agreed to keep, on request.
 *
 * Listing kept reports is a privacy surface, so the page is explicit about the boundary:
 * the backend hands out ids, clocks and provenance and nothing else, and removal here is
 * immediate rather than waiting for the window to close.
 */
export default function HistoryPage() {
  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-gray-900">Kept reports</h1>
        <p className="mt-2 text-sm text-gray-700">
          Nothing is stored unless the server allows history <em>and</em> the request asked to
          be kept. This page lists those reports by internal id so you can reopen one, or
          delete a copy you no longer want held.
        </p>
        <p className="mt-2 text-xs text-gray-600">
          Not sure what is stored and why?{' '}
          <Link
            href="/about/data"
            className="rounded font-medium text-blue-700 hover:underline focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Data governance
          </Link>
          .
        </p>
      </div>
      <HistoryList />
    </main>
  );
}
