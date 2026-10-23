import { MAX_PASSENGERS } from './types';
import type { JourneyInput, PassengerInput } from './types';

export interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

// Mirrors backend/railconfirm/domain/validation.py. Keeping the two in step is the
// point: a rule the client enforces differently from the server either blocks valid
// input or lets invalid input through to a 422 the user cannot connect to a field.
const TRAIN_NUMBER_RE = /^\d{4,6}$/;
const STATION_CODE_RE = /^[A-Z][A-Z0-9]{1,9}$/;
const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const MAX_STATUS_LENGTH = 120;

/**
 * True when an ISO-8601 string carries a UTC offset.
 *
 * The backend rejects a naive timestamp because an assumed zone shifts a lead time
 * by up to twelve hours, which is the resolution at which "was this known before
 * the chart?" is decided. A browser's datetime-local input produces no offset, so
 * the form must add the user's real one before sending.
 */
export function hasUtcOffset(value: string): boolean {
  if (!value) return false;
  return /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
}

/**
 * Convert a datetime-local value ("2026-10-21T08:00") into an offset-aware ISO
 * string using the viewer's actual zone. Returns null for an empty or unparseable
 * input rather than guessing a zone.
 */
export function toOffsetIso(localValue: string): string | null {
  const trimmed = localValue.trim();
  if (!trimmed) return null;
  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return null;
  // ISO string with the machine offset, e.g. 2026-10-21T08:00:00+05:30
  const local = new Date(parsed.getTime() - parsed.getTimezoneOffset() * 60000);
  const iso = local.toISOString();
  const offsetMinutes = -parsed.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absolute = Math.abs(offsetMinutes);
  const hh = String(Math.floor(absolute / 60)).padStart(2, '0');
  const mm = String(absolute % 60).padStart(2, '0');
  return `${iso.slice(0, 19)}${sign}${hh}:${mm}`;
}

/** Today's date as YYYY-MM-DD, in the viewer's zone. */
export function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function validateJourney(
  journey: Partial<JourneyInput>,
  predictionAt: string,
): ValidationResult {
  const errors: Record<string, string> = {};

  const trainNumber = (journey.train_number ?? '').trim();
  if (!trainNumber) {
    errors.train_number = 'Train number is required.';
  } else if (!TRAIN_NUMBER_RE.test(trainNumber)) {
    errors.train_number = 'Train number must be 4–6 digits.';
  }

  if (!journey.journey_date || !ISO_DATE_RE.test(journey.journey_date)) {
    errors.journey_date = 'Journey date must be a calendar date as YYYY-MM-DD.';
  }

  for (const key of ['boarding_station', 'destination_station'] as const) {
    const value = (journey[key] ?? '').trim();
    if (!value) {
      errors[key] = `${key === 'boarding_station' ? 'Boarding' : 'Destination'} station code is required.`;
    } else if (!STATION_CODE_RE.test(value.toUpperCase())) {
      errors[key] = 'Station code must be 2–10 characters, starting with a letter (e.g. NDLS, MAS).';
    }
  }

  const boarding = (journey.boarding_station ?? '').trim().toUpperCase();
  const destination = (journey.destination_station ?? '').trim().toUpperCase();
  if (boarding && destination && boarding === destination && !errors.destination_station) {
    errors.destination_station = 'Destination must differ from the boarding station.';
  }

  if (!journey.class_code) errors.class_code = 'Travel class is required.';
  if (!journey.quota_code) errors.quota_code = 'Quota is required.';

  // The server requires an offset-aware prediction timestamp earlier than the
  // journey date; the client can say which of the two is wrong.
  if (!predictionAt) {
    errors.prediction_at = 'Prediction time is required.';
  } else if (!hasUtcOffset(predictionAt)) {
    errors.prediction_at =
      'Prediction time must include a UTC offset. Choose the date and time; the offset is added automatically.';
  } else if (journey.journey_date && ISO_DATE_RE.test(journey.journey_date)) {
    const predictionDay = predictionAt.slice(0, 10);
    if (predictionDay >= journey.journey_date) {
      errors.prediction_at =
        'Prediction time must fall before the journey date. From the travel day onward the outcome is no longer a forecast.';
    }
  }

  return { isValid: Object.keys(errors).length === 0, errors };
}

export function validatePassengers(passengers: PassengerInput[]): ValidationResult {
  const errors: Record<string, string> = {};

  if (passengers.length === 0) {
    errors.passengers = 'At least one passenger is required.';
    return { isValid: false, errors };
  }
  if (passengers.length > MAX_PASSENGERS) {
    errors.passengers = `At most ${MAX_PASSENGERS} passengers are supported in one request.`;
  }

  passengers.forEach((passenger, index) => {
    const label = `Passenger ${index + 1}`;
    for (const key of ['original_status', 'current_status'] as const) {
      const value = passenger[key];
      if (!value || value.trim() === '') {
        errors[`passengers[${index}].${key}`] =
          `${label}: ${key === 'original_status' ? 'status as booked' : 'current status'} is required.`;
      } else if (value.length > MAX_STATUS_LENGTH) {
        errors[`passengers[${index}].${key}`] =
          `${label}: status must be ${MAX_STATUS_LENGTH} characters or fewer.`;
      }
    }

    const observed = passenger.current_status_observed_at;
    if (observed) {
      if (!hasUtcOffset(observed)) {
        errors[`passengers[${index}].current_status_observed_at`] =
          `${label}: observation time must include a UTC offset.`;
      } else if (Number.isNaN(Date.parse(observed))) {
        errors[`passengers[${index}].current_status_observed_at`] =
          `${label}: observation time is not a valid date and time.`;
      }
    }
  });

  return { isValid: Object.keys(errors).length === 0, errors };
}

/**
 * Server field paths (dotted, relative to the body) mapped onto the keys this
 * form uses, so a 422 marks the input the user actually has to fix.
 */
export function serverFieldToLocalKey(field: string): string | null {
  const match = field.match(/^passengers\.(\d+)\.(.+)$/);
  if (match) {
    return `passengers[${match[1]}].${match[2]}`;
  }
  const stripped = field.replace(/^journey\./, '');
  const known = [
    'train_number',
    'journey_date',
    'boarding_station',
    'destination_station',
    'class_code',
    'quota_code',
    'prediction_at',
    'target',
    'passengers',
  ];
  return known.includes(stripped) ? stripped : null;
}
