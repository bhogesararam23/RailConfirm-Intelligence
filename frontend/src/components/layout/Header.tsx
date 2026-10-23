import React from 'react';
import Link from 'next/link';

export function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 rounded focus:outline-none focus:ring-2 focus:ring-blue-500">
          <span className="text-xl font-bold tracking-tight text-gray-900">
            RailConfirm <span className="text-blue-600">Intelligence</span>
          </span>
          <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
            Local data only
          </span>
        </Link>
        <nav aria-label="Primary" className="flex items-center gap-4 text-sm font-medium text-gray-600">
          <Link href="/" className="rounded hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500">
            Predictor
          </Link>
          <Link
            href="/about/methodology"
            className="rounded hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Methodology
          </Link>
          <Link
            href="/about/data"
            className="rounded hover:text-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            Data governance
          </Link>
        </nav>
      </div>
    </header>
  );
}
