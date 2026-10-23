import type { NormalizedStatus } from './types';

export interface StatusDisplayInfo {
  label: string;
  shortLabel: string;
  colorClass: string;
  textClass: string;
  borderClass: string;
  ariaLabel: string;
}

/**
 * Display metadata for a normalized status.
 *
 * Colour always accompanies text: a status that is only distinguishable by hue is
 * not accessible, and these categories are frequently adjacent on the same screen.
 */
export function getStatusDisplay(status: NormalizedStatus): StatusDisplayInfo {
  switch (status) {
    case 'CNF':
      return {
        label: 'CNF — Confirmed berth',
        shortLabel: 'CNF',
        colorClass: 'bg-green-100',
        textClass: 'text-green-800',
        borderClass: 'border-green-300',
        ariaLabel: 'Status: confirmed berth',
      };
    case 'RAC':
      return {
        label: 'RAC — Reservation Against Cancellation',
        shortLabel: 'RAC',
        colorClass: 'bg-yellow-100',
        textClass: 'text-yellow-800',
        borderClass: 'border-yellow-300',
        ariaLabel: 'Status: RAC, seated travel authorisation',
      };
    case 'WL':
      return {
        label: 'WL — Waitlisted',
        shortLabel: 'WL',
        colorClass: 'bg-orange-100',
        textClass: 'text-orange-800',
        borderClass: 'border-orange-300',
        ariaLabel: 'Status: waitlisted',
      };
    case 'CANCELLED':
      return {
        label: 'Cancelled',
        shortLabel: 'CAN',
        colorClass: 'bg-red-100',
        textClass: 'text-red-800',
        borderClass: 'border-red-300',
        ariaLabel: 'Status: cancelled',
      };
    case 'CENSORED':
      return {
        label: 'Censored — outcome not observed',
        shortLabel: 'CSR',
        colorClass: 'bg-purple-100',
        textClass: 'text-purple-800',
        borderClass: 'border-purple-300',
        ariaLabel: 'Status: censored, outcome was not observed',
      };
    case 'OTHER':
      return {
        label: 'Other recognised state',
        shortLabel: 'OTH',
        colorClass: 'bg-gray-100',
        textClass: 'text-gray-700',
        borderClass: 'border-gray-300',
        ariaLabel: 'Status: other recognised state',
      };
    case 'UNKNOWN':
    default:
      return {
        label: 'Unknown status',
        shortLabel: 'UNK',
        colorClass: 'bg-gray-100',
        textClass: 'text-gray-600',
        borderClass: 'border-gray-300',
        ariaLabel: 'Status: not recognised by the mapping',
      };
  }
}

/**
 * Format a probability for display.
 *
 * null renders as an em dash, never as 0%. "No estimate" and "0% chance" are
 * different claims, and the earlier `((x || 0) * 100).toFixed(1)` idiom rendered a
 * missing value as a confident zero.
 */
export function formatProbability(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  if (!Number.isFinite(value)) return '—';
  const percent = value * 100;
  // A single decimal invites reading precision the evidence does not support;
  // two is enough to keep small probabilities distinguishable from zero.
  if (percent > 0 && percent < 0.1) return '<0.1%';
  return `${percent.toFixed(1)}%`;
}

/** Format an ISO-8601 timestamp in IST, which is the zone the journey happens in. */
export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return (
      date.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }) + ' IST'
    );
  } catch {
    return iso;
  }
}

export function formatEvidenceCoverage(coverage: string): string {
  switch (coverage) {
    case 'sufficient':
      return 'Every passenger has an estimate';
    case 'partial':
      return 'Some passengers have estimates, others abstain';
    case 'insufficient':
      return 'No estimate available';
    default:
      return coverage;
  }
}

/**
 * Readable cohort evidence, e.g. "SL/GN/WL, 105 records (exact status match)".
 * The backend records this so a broad-cohort fallback is not presented as a
 * cohort-specific result.
 */
export function describeBasis(basis: string | null | undefined): string {
  if (!basis) return 'No evidence cohort recorded.';
  const cohort = /cohort=([^\s]+)/.exec(basis)?.[1] ?? '';
  const n = /n=(\d+)/.exec(basis)?.[1] ?? '';
  const fallback = basis.includes('exact_status_match=false');
  const parts = [
    cohort ? `Cohort ${cohort.split('/').join(' / ')}` : 'Cohort unnamed',
    n ? `${n} historical records` : 'record count unavailable',
    fallback
      ? 'broad fallback, not a status-specific match'
      : 'exact status match',
  ];
  return parts.join(' — ') + '.';
}
