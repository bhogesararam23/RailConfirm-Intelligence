import { describe, expect, it } from 'vitest';
import {
  describeBasis,
  formatEvidenceCoverage,
  formatProbability,
  formatTimestamp,
  getStatusDisplay,
} from '@/lib/statusUtils';
import { ABSTENTION_MESSAGES } from '@/lib/types';
import type { AbstentionReason } from '@/lib/types';

describe('formatProbability', () => {
  it('renders a missing estimate as a dash, never as zero', () => {
    // The bug this replaces was `(x || 0) * 100).toFixed(1)`, which printed "0.0%"
    // for a value the backend deliberately did not supply.
    expect(formatProbability(null)).toBe('—');
    expect(formatProbability(undefined)).toBe('—');
    expect(formatProbability(Number.NaN)).toBe('—');
  });

  it('keeps a genuine zero distinguishable from a missing value', () => {
    expect(formatProbability(0)).toBe('0.0%');
  });

  it.each([
    [1, '100.0%'],
    [0.6454545, '64.5%'],
    [0.5, '50.0%'],
  ])('formats %s as %s', (value, expected) => {
    expect(formatProbability(value)).toBe(expected);
  });

  it('does not render a tiny probability as zero', () => {
    expect(formatProbability(0.0002)).toBe('<0.1%');
  });

  it('refuses to present a non-finite value as a percentage', () => {
    expect(formatProbability(Number.POSITIVE_INFINITY)).toBe('—');
  });
});

describe('describeBasis', () => {
  it('names the cohort, the sample size and whether it matched exactly', () => {
    expect(
      describeBasis('cohort=SL/GN/WL n=105 exact_status_match=true'),
    ).toBe('Cohort SL / GN / WL — 105 historical records — exact status match.');
  });

  it('says plainly when a broad fallback produced the number', () => {
    const text = describeBasis(
      "cohort=SL/GN/ALL n=320 exact_status_match=false (broad ALL cohort fallback)",
    );
    expect(text).toContain('broad fallback');
    expect(text).toContain('320 historical records');
  });

  it('reports a missing basis rather than inventing one', () => {
    expect(describeBasis(null)).toBe('No evidence cohort recorded.');
  });
});

describe('formatTimestamp', () => {
  it('renders an instant in IST, the zone the journey happens in', () => {
    const rendered = formatTimestamp('2026-12-10T02:30:00Z');
    expect(rendered).toContain('IST');
    expect(rendered).toContain('08:00');
  });

  it('returns a dash for a missing timestamp and the input for an unparseable one', () => {
    expect(formatTimestamp(null)).toBe('—');
    expect(formatTimestamp('tomorrow')).toBe('tomorrow');
  });
});

describe('formatEvidenceCoverage', () => {
  it('distinguishes partial from insufficient', () => {
    expect(formatEvidenceCoverage('partial')).toMatch(/Some passengers/);
    expect(formatEvidenceCoverage('insufficient')).toMatch(/No estimate/);
    expect(formatEvidenceCoverage('sufficient')).toMatch(/Every passenger/);
  });
});

describe('status display', () => {
  it('pairs every colour with text and an aria description', () => {
    for (const status of ['CNF', 'RAC', 'WL', 'CANCELLED', 'CENSORED', 'OTHER', 'UNKNOWN'] as const) {
      const display = getStatusDisplay(status);
      expect(display.label).not.toBe('');
      expect(display.ariaLabel).toMatch(/^Status:/);
    }
  });

  it('keeps censored distinct from a negative outcome', () => {
    expect(getStatusDisplay('CENSORED').label).toMatch(/not observed/);
  });
});

describe('ABSTENTION_MESSAGES', () => {
  it('carries text for every reason code the backend can send', () => {
    const emitted: AbstentionReason[] = [
      'unknown_status',
      'unsupported_status',
      'unsupported_class',
      'unsupported_quota',
      'no_trained_model',
      'no_approved_data',
      'model_artifact_invalid',
      'insufficient_sample',
      'invalid_input',
    ];
    for (const reason of emitted) {
      expect(ABSTENTION_MESSAGES[reason], reason).toBeTruthy();
    }
  });

  it('does not describe no_approved_data with the no-model wording', () => {
    // A missing entry used to fall back to "no trained model", telling the user
    // the wrong thing was unfinished.
    expect(ABSTENTION_MESSAGES.no_approved_data).toMatch(/approved/);
    expect(ABSTENTION_MESSAGES.model_artifact_invalid).toMatch(/validation|configured/);
    expect(ABSTENTION_MESSAGES.unsupported_quota).toMatch(/quota/);
  });
});
