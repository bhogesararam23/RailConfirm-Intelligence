// Journey input
export interface JourneyInput {
  train_number: string; // 4-6 digit string
  journey_date: string; // YYYY-MM-DD
  boarding_station: string; // Station code (uppercase)
  destination_station: string; // Station code (uppercase)
  class_code: string; // e.g. "SL", "3A", "2A", "1A"
  quota_code: string; // e.g. "GN", "TQ"
}

// Passenger input - preserve original vs latest separately
export interface PassengerInput {
  original_status: string; // As booked
  current_status: string; // Latest observed
  current_status_observed_at?: string; // ISO-8601 or undefined (user may not know)
  status_time_unknown?: boolean; // Explicit unknown-time state
}

// Prediction request
export interface PredictionRequest {
  journey: JourneyInput;
  prediction_at: string; // ISO-8601 timestamp
  passengers: PassengerInput[];
}

// Normalized status (from backend)
export type NormalizedStatus =
  | 'CNF'
  | 'RAC'
  | 'WL'
  | 'CANCELLED'
  | 'OTHER'
  | 'UNKNOWN'
  | 'CENSORED';

// Passenger outcome
export interface PassengerOutcome {
  passenger_id: string;
  p_cnf: number | null;
  p_rac: number | null;
  p_wl: number | null;
  p_cancelled: number | null;
  p_other: number | null;
  is_supported: boolean;
  abstention_reason?: string;
  observed_status: {
    raw: string;
    normalized: NormalizedStatus;
    position?: number;
    wl_category?: string;
  };
}

// Group outcome
export interface GroupOutcome {
  p_all_cnf: number | null;
  p_all_cnf_or_rac: number | null;
  p_at_least_one_wl: number | null;
  method: string;
  assumptions: string;
  is_supported: boolean;
  abstention_reason?: string;
}

// Full prediction response
export interface PredictionResponse {
  prediction_id: string;
  target_definition: string;
  prediction_at: string;
  created_at: string;
  model_version: string;
  feature_schema_version: string;
  evidence_coverage: 'sufficient' | 'insufficient' | 'partial';
  is_supported: boolean;
  passenger_outcomes: PassengerOutcome[];
  group_outcome?: GroupOutcome;
  limitations: string[];
  warnings: string[];
}

// API error shape (as received from server JSON)
export interface APIErrorShape {
  error: string;
  code: string;
  detail?: string;
}

// Abstention reason display messages
export const ABSTENTION_MESSAGES: Record<string, string> = {
  no_trained_model:
    'No prediction model is available yet. The system will return estimates when a validated model has been trained on approved data.',
  unsupported_status:
    'This ticket status category is not yet supported by the prediction model.',
  unsupported_class:
    'This travel class is not yet covered by the prediction model.',
  insufficient_sample:
    'There is insufficient historical data for this ticket category to produce a reliable estimate.',
  unknown_status:
    'The entered ticket status could not be recognized. Please check the status code.',
  invalid_input:
    'The input could not be validated. Please check all fields.',
};

// Class codes
export const CLASS_CODES = {
  '1A': 'First AC (1A)',
  '2A': 'Second AC (2A)',
  '3A': 'Third AC (3A)',
  '3E': 'Third AC Economy (3E)',
  SL: 'Sleeper (SL)',
  CC: 'Chair Car (CC)',
  EC: 'Executive Chair Car (EC)',
  '2S': 'Second Sitting (2S)',
  FC: 'First Class (FC)',
} as const;

// Quota codes
export const QUOTA_CODES = {
  GN: 'General (GN)',
  TQ: 'Tatkal (TQ)',
  PT: 'Premium Tatkal (PT)',
  LD: 'Ladies (LD)',
  DF: 'Defence (DF)',
  SS: 'Senior Citizen (SS)',
  HP: 'Handicapped (HP)',
} as const;

export type ClassCode = keyof typeof CLASS_CODES;
export type QuotaCode = keyof typeof QUOTA_CODES;
