import React from 'react';
import Link from 'next/link';

export function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="text-xl font-bold tracking-tight text-gray-900">
            RailConfirm <span className="text-blue-600">Intelligence</span>
          </span>
          <span className="rounded bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
            Local-First
          </span>
        </Link>
        <nav className="flex items-center gap-4 text-sm font-medium text-gray-600">
          <Link href="/" className="hover:text-blue-600">
            Predictor
          </Link>
          <Link href="/about/methodology" className="hover:text-blue-600">
            Methodology
          </Link>
          <Link href="/about/data" className="hover:text-blue-600">
            Data Governance
          </Link>
        </nav>
      </div>
    </header>
  );
}
