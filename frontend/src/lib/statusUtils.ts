import type { NormalizedStatus } from './types';

export interface StatusDisplayInfo {
  label: string;
  shortLabel: string;
  colorClass: string; // Tailwind bg class
  textClass: string; // Tailwind text class
  borderClass: string; // Tailwind border class
  ariaLabel: string;
}

/**
 * Returns display metadata for a normalized status code.
 * Colors are supplemented by text labels — never rely on color alone (FRONTEND_GUIDE.md).
 */
export function getStatusDisplay(status: NormalizedStatus): StatusDisplayInfo {
  switch (status) {
    case 'CNF':
      return {
        label: 'CNF — Confirmed',
        shortLabel: 'CNF',
        colorClass: 'bg-green-100',
        textClass: 'text-green-800',
        borderClass: 'border-green-300',
        ariaLabel: 'Status: Confirmed',
      };
    case 'RAC':
      return {
        label: 'RAC — RAC Accommodation',
        shortLabel: 'RAC',
        colorClass: 'bg-yellow-100',
        textClass: 'text-yellow-800',
        borderClass: 'border-yellow-300',
        ariaLabel: 'Status: RAC (Reservation Against Cancellation)',
      };
    case 'WL':
      return {
        label: 'WL — Waitlisted',
        shortLabel: 'WL',
        colorClass: 'bg-orange-100',
        textClass: 'text-orange-800',
        borderClass: 'border-orange-300',
        ariaLabel: 'Status: Waitlisted',
      };
    case 'CANCELLED':
      return {
        label: 'Cancelled',
        shortLabel: 'CAN',
        colorClass: 'bg-red-100',
        textClass: 'text-red-800',
        borderClass: 'border-red-300',
        ariaLabel: 'Status: Cancelled',
      };
    case 'CENSORED':
      return {
        label: 'Censored — outcome not observed',
        shortLabel: 'CSR',
        colorClass: 'bg-purple-100',
        textClass: 'text-purple-800',
        borderClass: 'border-purple-300',
        ariaLabel: 'Status: Censored (outcome not observed)',
      };
    case 'OTHER':
      return {
        label: 'Other',
        shortLabel: 'OTH',
        colorClass: 'bg-gray-100',
        textClass: 'text-gray-700',
        borderClass: 'border-gray-300',
        ariaLabel: 'Status: Other',
      };
    case 'UNKNOWN':
    default:
      return {
        label: 'Unknown status',
        shortLabel: 'UNK',
        colorClass: 'bg-gray-100',
        textClass: 'text-gray-600',
        borderClass: 'border-gray-300',
        ariaLabel: 'Status: Unknown',
      };
  }
}

/**
 * Format a probability (0–1 float) as a percentage string for display.
 * Returns '—' for null values.
 */
export function formatProbability(value: number | null): string {
  if (value === null) return '—';
  return `${Math.round(value * 100)}%`;
}

/**
 * Format an ISO-8601 timestamp for display in IST-friendly format.
 * Falls back to raw string on parse failure.
 */
export function formatTimestamp(iso: string): string {
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('en-IN', {
      timeZone: 'Asia/Kolkata',
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    }) + ' IST';
  } catch {
    return iso;
  }
}

/**
 * Returns a human-readable evidence coverage label.
 */
export function formatEvidenceCoverage(
  coverage: 'sufficient' | 'insufficient' | 'partial',
): string {
  switch (coverage) {
    case 'sufficient':
      return 'Sufficient evidence';
    case 'partial':
      return 'Partial evidence';
    case 'insufficient':
      return 'Insufficient evidence';
    default:
      return coverage;
  }
}
