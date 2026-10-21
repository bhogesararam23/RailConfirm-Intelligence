import type { JourneyInput, PassengerInput } from './types';

export interface ValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

const TRAIN_NUMBER_RE = /^\d{4,6}$/;
const STATION_CODE_RE = /^[A-Z]{1,10}$/;

/**
 * Validates journey-level fields.
 * Returns a ValidationResult with an errors map keyed by field name.
 */
export function validateJourney(
  journey: Partial<JourneyInput>,
): ValidationResult {
  const errors: Record<string, string> = {};

  // train_number
  if (!journey.train_number || journey.train_number.trim() === '') {
    errors.train_number = 'Train number is required.';
  } else if (!TRAIN_NUMBER_RE.test(journey.train_number.trim())) {
    errors.train_number = 'Train number must be 4–6 digits.';
  }

  // journey_date
  if (!journey.journey_date || journey.journey_date.trim() === '') {
    errors.journey_date = 'Journey date is required.';
  } else {
    const d = new Date(journey.journey_date);
    if (isNaN(d.getTime())) {
      errors.journey_date = 'Journey date is not a valid date.';
    } else {
      const twoYearsAgo = new Date();
      twoYearsAgo.setFullYear(twoYearsAgo.getFullYear() - 2);
      if (d < twoYearsAgo) {
        errors.journey_date =
          'Journey date is more than 2 years in the past. Historical queries are limited to 2 years.';
      }
    }
  }

  // boarding_station
  if (!journey.boarding_station || journey.boarding_station.trim() === '') {
    errors.boarding_station = 'Boarding station code is required.';
  } else if (!STATION_CODE_RE.test(journey.boarding_station.trim())) {
    errors.boarding_station =
      'Station code must be 1–10 uppercase letters (e.g. NDLS, MAS).';
  }

  // destination_station
  if (
    !journey.destination_station ||
    journey.destination_station.trim() === ''
  ) {
    errors.destination_station = 'Destination station code is required.';
  } else if (!STATION_CODE_RE.test(journey.destination_station.trim())) {
    errors.destination_station =
      'Station code must be 1–10 uppercase letters (e.g. NDLS, MAS).';
  } else if (
    journey.boarding_station &&
    journey.destination_station.trim() ===
      journey.boarding_station.trim()
  ) {
    errors.destination_station =
      'Destination station must differ from boarding station.';
  }

  // class_code
  if (!journey.class_code || journey.class_code.trim() === '') {
    errors.class_code = 'Travel class is required.';
  }

  // quota_code
  if (!journey.quota_code || journey.quota_code.trim() === '') {
    errors.quota_code = 'Quota is required.';
  }

  return { isValid: Object.keys(errors).length === 0, errors };
}

/**
 * Validates passenger rows.
 * Returns errors keyed as `passengers[i].fieldName`.
 */
export function validatePassengers(
  passengers: PassengerInput[],
): ValidationResult {
  const errors: Record<string, string> = {};

  if (passengers.length === 0) {
    errors.passengers = 'At least one passenger is required.';
    return { isValid: false, errors };
  }

  passengers.forEach((p, i) => {
    if (!p.original_status || p.original_status.trim() === '') {
      errors[`passengers[${i}].original_status`] =
        `Passenger ${i + 1}: Original status (as booked) is required.`;
    }
    if (!p.current_status || p.current_status.trim() === '') {
      errors[`passengers[${i}].current_status`] =
        `Passenger ${i + 1}: Current/latest status is required.`;
    }
    // If time is provided but status_time_unknown is not set, validate the timestamp format
    if (
      p.current_status_observed_at &&
      !p.status_time_unknown
    ) {
      const ts = new Date(p.current_status_observed_at);
      if (isNaN(ts.getTime())) {
        errors[`passengers[${i}].current_status_observed_at`] =
          `Passenger ${i + 1}: Observation time is not a valid date/time.`;
      }
    }
  });

  return { isValid: Object.keys(errors).length === 0, errors };
}
