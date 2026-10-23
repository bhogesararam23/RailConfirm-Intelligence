import { describe, expect, it } from 'vitest';
import {
  hasUtcOffset,
  serverFieldToLocalKey,
  toOffsetIso,
  validateJourney,
  validatePassengers,
} from '@/lib/validation';
import { MAX_PASSENGERS } from '@/lib/types';
import type { JourneyInput, PassengerInput } from '@/lib/types';

const journey = (overrides: Partial<JourneyInput> = {}): JourneyInput => ({
  train_number: '12301',
  journey_date: '2026-12-20',
  boarding_station: 'NDLS',
  destination_station: 'HWH',
  class_code: 'SL',
  quota_code: 'GN',
  ...overrides,
});

const passenger = (overrides: Partial<PassengerInput> = {}): PassengerInput => ({
  original_status: 'GNWL/45',
  current_status: 'GNWL/12',
  current_status_observed_at: '2026-12-10T08:00:00+05:30',
  ...overrides,
});

describe('hasUtcOffset', () => {
  it.each([
    ['2026-12-10T08:00:00Z', true],
    ['2026-12-10T08:00:00+05:30', true],
    ['2026-12-10T08:00:00-08:00', true],
    ['2026-12-10T08:00:00', false],
    ['2026-12-10', false],
    ['', false],
  ])('%s → offset %s', (value, expected) => {
    expect(hasUtcOffset(value)).toBe(expected);
  });
});

describe('toOffsetIso', () => {
  it('attaches an offset to a datetime-local value', () => {
    const iso = toOffsetIso('2026-12-10T08:00');
    expect(iso).not.toBeNull();
    expect(hasUtcOffset(iso as string)).toBe(true);
    expect(iso).toMatch(/^2026-12-10T08:00:00[+-]\d{2}:\d{2}$/);
  });

  it('returns null instead of guessing for empty or broken input', () => {
    expect(toOffsetIso('')).toBeNull();
    expect(toOffsetIso('   ')).toBeNull();
    expect(toOffsetIso('not-a-time')).toBeNull();
  });
});

describe('validateJourney', () => {
  const at = '2026-12-10T08:00:00+05:30';

  it('accepts a well-formed journey with an offset-aware prediction time', () => {
    expect(validateJourney(journey(), at)).toEqual({ isValid: true, errors: {} });
  });

  it('rejects a prediction time without an offset', () => {
    const result = validateJourney(journey(), '2026-12-10T08:00:00');
    expect(result.isValid).toBe(false);
    expect(result.errors.prediction_at).toMatch(/UTC offset/);
  });

  it('rejects a prediction at or after the journey date', () => {
    expect(validateJourney(journey(), '2026-12-20T01:00:00Z').errors.prediction_at).toMatch(
      /before the journey date/,
    );
    expect(validateJourney(journey(), '2026-12-27T01:00:00Z').errors.prediction_at).toMatch(
      /before the journey date/,
    );
  });

  it.each([
    ['123', 'train_number'],
    ['1234567', 'train_number'],
    ['12A01', 'train_number'],
  ])('rejects train number %s', (value, key) => {
    expect(validateJourney(journey({ train_number: value }), at).errors[key]).toBeDefined();
  });

  it.each(['N', 'NDLS!', 'TOO_LONG_STATION_CODE'])('rejects station code %s', (value) => {
    expect(
      validateJourney(journey({ boarding_station: value }), at).errors.boarding_station,
    ).toBeDefined();
  });

  it('rejects identical boarding and destination stations', () => {
    const result = validateJourney(
      journey({ boarding_station: 'NDLS', destination_station: 'NDLS' }),
      at,
    );
    expect(result.errors.destination_station).toMatch(/differ/);
  });

  it('accepts a station code containing digits after a leading letter', () => {
    expect(validateJourney(journey({ destination_station: 'NDLS1' }), at).isValid).toBe(true);
  });

  it('requires an ISO calendar journey date', () => {
    expect(validateJourney(journey({ journey_date: '20/12/2026' }), at).errors.journey_date).toBeDefined();
  });
});

describe('validatePassengers', () => {
  it('requires at least one passenger', () => {
    expect(validatePassengers([]).errors.passengers).toMatch(/At least one/);
  });

  it('rejects more than the documented maximum', () => {
    const rows = Array.from({ length: MAX_PASSENGERS + 1 }, () => passenger());
    expect(validatePassengers(rows).errors.passengers).toMatch(/At most 6/);
  });

  it.each(['', '   '])('rejects blank status %j', (value) => {
    const result = validatePassengers([passenger({ current_status: value })]);
    expect(result.errors['passengers[0].current_status']).toBeDefined();
  });

  it('rejects an over-long status string', () => {
    const result = validatePassengers([passenger({ current_status: 'GNWL/' + '9'.repeat(200) })]);
    expect(result.errors['passengers[0].current_status']).toMatch(/characters/);
  });

  it('rejects a naive observation time', () => {
    const result = validatePassengers([passenger({ current_status_observed_at: '2026-12-10T08:00:00' })]);
    expect(result.errors['passengers[0].current_status_observed_at']).toMatch(/offset/);
  });

  it('accepts an omitted observation time', () => {
    expect(validatePassengers([passenger({ current_status_observed_at: null })]).isValid).toBe(true);
  });
});

describe('serverFieldToLocalKey', () => {
  it('maps dotted passenger paths onto form keys', () => {
    expect(serverFieldToLocalKey('passengers.2.current_status')).toBe(
      'passengers[2].current_status',
    );
  });

  it('strips the journey prefix', () => {
    expect(serverFieldToLocalKey('journey.train_number')).toBe('train_number');
    expect(serverFieldToLocalKey('prediction_at')).toBe('prediction_at');
  });

  it('returns null for a path the form has no field for', () => {
    expect(serverFieldToLocalKey('some_future_field')).toBeNull();
  });
});
