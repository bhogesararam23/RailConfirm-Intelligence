// Types mirroring backend/railconfirm/api/v1/schemas.py.
//
// These must stay in step with the server. The backend is the source of truth:
// docs/architecture/API_CONTRACT.md lists every field, and
// backend/tests/api/test_contract.py asserts the OpenAPI surface. If a field is
// absent here, the backend does not send it.

/** Broad normalized status categories produced by the versioned status mapping. */
export type NormalizedStatus =
  | 'CNF'
  | 'RAC'
  | 'WL'
  | 'CANCELLED'
  | 'OTHER'
  | 'UNKNOWN'
  | 'CENSORED';

/** Prediction targets the API accepts. Each names a different outcome moment. */
export type PredictionTarget = 'final_chart_cnf' | 'final_chart_cnf_or_rac';

/** Registry resolution state, mirrored from ArtifactStatus in the backend. */
export type RegistryStatus =
  | 'no_active_version'
  | 'artifact_missing'
  | 'artifact_invalid'
  | 'not_promoted'
  | 'data_not_approved'
  | 'ready';

/** Evidence coverage: all passengers supported, some, or none. */
export type EvidenceCoverage = 'sufficient' | 'partial' | 'insufficient';

export interface JourneyInput {
  train_number: string; // 4–6 digits
  journey_date: string; // YYYY-MM-DD
  boarding_station: string; // 2–10 uppercase letters/digits
  destination_station: string;
  class_code: string;
  quota_code: string;
}

export interface PassengerInput {
  original_status: string;
  current_status: string;
  /**
   * ISO-8601 **with a UTC offset**, or omitted when the time is unknown. A naive
   * timestamp is rejected by the backend: without an offset it cannot be compared
   * against the prediction cutoff.
   */
  current_status_observed_at?: string | null;
}

export interface PredictionRequest {
  journey: JourneyInput;
  prediction_at: string; // ISO-8601 with offset, before journey_date
  target?: PredictionTarget;
  passengers: PassengerInput[]; // 1–6 entries
  /**
   * Ask the backend to keep this report. Only honoured when the server has history
   * enabled; `stored` in the response is the answer, not this field.
   */
  persist?: boolean;
}

/**
 * Per-passenger outcome. When `is_supported` is false every probability is null;
 * when true all five are non-null and sum to 1. A client must not turn a null
 * into 0 — "no estimate" and "zero chance" are different claims.
 */
export interface PassengerOutcome {
  passenger_id: string;
  original_status: string;
  original_status_normalized: NormalizedStatus;
  current_status: string;
  current_status_normalized: NormalizedStatus;
  p_cnf: number | null;
  p_rac: number | null;
  p_wl: number | null;
  p_cancelled: number | null;
  p_other: number | null;
  is_supported: boolean;
  abstention_reason: AbstentionReason | null;
  /** Evidence cohort and sample size, e.g. "cohort=SL/GN/WL n=105 exact_status_match=true". */
  basis: string | null;
  parse_warnings: string[];
}

export interface GroupOutcome {
  p_all_cnf: number | null;
  p_all_cnf_or_rac: number | null;
  p_at_least_one_wl: number | null;
  method: 'single_passenger' | 'independence_baseline' | 'insufficient_data' | string;
  assumptions: string;
  is_supported: boolean;
  abstention_reason: AbstentionReason | null;
}

export interface PredictionResponse {
  prediction_id: string;
  target: PredictionTarget;
  target_definition: string;
  prediction_at: string;
  created_at: string;
  model_version: string;
  registry_status: RegistryStatus;
  feature_schema_version: string;
  evidence_coverage: EvidenceCoverage;
  /** True when at least one passenger has an estimate. See evidence_coverage for the rest. */
  is_supported: boolean;
  passenger_count: number;
  passenger_outcomes: PassengerOutcome[];
  group_outcome: GroupOutcome | null;
  limitations: string[];
  warnings: string[];
  outcome_classes: string;
  /** True only when the backend actually kept a copy. `persist: true` alone means nothing. */
  stored: boolean;
  /** Path to reopen this report, e.g. `/v1/predictions/<uuid>`. Null when not stored. */
  report_url: string | null;
  /** ISO-8601 with offset. After this the id stops resolving, so a bookmark is not an archive. */
  retention_expires_at: string | null;
}

/** Codes the error envelope uses for history problems. */
export type HistoryErrorCode = 'not_found' | 'history_disabled' | 'storage_unavailable';

/**
 * One kept report, as the history list describes it.
 *
 * Mirrors `api/v1/schemas.py::StoredReportSummary`. The list carries no journey, no
 * probabilities and no statuses on purpose: it exists so a user can find and remove a
 * report, not so a page can display ticket detail without opening it.
 */
export interface StoredReportSummary {
  prediction_id: string;
  target: string;
  model_version: string;
  recorded_at: string;
  retention_expires_at: string;
}

/** What `GET /v1/predictions` returns. `count` equals `reports.length`. */
export interface StoredReportsResponse {
  reports: StoredReportSummary[];
  count: number;
  retention_days: number;
}

export interface HealthResponse {
  status: string;
  model_version: string;
  data_version: string;
  app_version: string;
  model_available: boolean;
  registry_status: RegistryStatus;
  limits: Record<string, number | string>;
  /**
   * Empty when this server keeps no history at all — the default. When present it
   * carries `enabled`, `retention_days` and `stored_reports`, because a page that
   * offers to save should say whether saving is possible here.
   */
  prediction_history?: Record<string, boolean | number | string>;
}

/** One field-level problem in a failed request. */
export interface ErrorDetail {
  code: string;
  message: string;
  field: string | null;
}

/** The documented error envelope for every handled API error. */
export interface ApiErrorBody {
  error: string;
  details: ErrorDetail[];
  request_id: string | null;
}

export type AbstentionReason =
  | 'unknown_status'
  | 'unsupported_status'
  | 'unsupported_class'
  | 'unsupported_quota'
  | 'no_trained_model'
  | 'no_approved_data'
  | 'model_artifact_invalid'
  | 'insufficient_sample'
  | 'invalid_input';

/**
 * Display text for each abstention reason. Every value the backend can send must
 * appear here: a missing entry silently falls back to text describing a
 * different problem, which tells the user the wrong reason.
 */
export const ABSTENTION_MESSAGES: Record<AbstentionReason, string> = {
  unknown_status:
    'The ticket status you entered has no verified meaning yet, so it cannot be classified. Check the code, or leave it for review.',
  unsupported_status:
    'This status is recognised but sits outside the population this estimate covers — a cancelled or censored booking is no longer competing for a berth.',
  unsupported_class:
    'This travel class is not covered by the available evidence.',
  unsupported_quota:
    'This booking quota is not covered by the available evidence.',
  no_trained_model:
    'No validated model has been promoted for this target, so the system will not invent a percentage.',
  no_approved_data:
    'No historical dataset has been approved for this purpose yet, so there is no evidence base to estimate from.',
  model_artifact_invalid:
    'A model was configured but failed validation, so it is not being used. This is reported rather than falling back silently.',
  insufficient_sample:
    'Too few matching historical records exist for this category to report a probability honestly.',
  invalid_input:
    'The request could not be turned into a valid prediction input. Check the reported fields.',
};

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

export const QUOTA_CODES = {
  GN: 'General (GN)',
  TQ: 'Tatkal (TQ)',
  PT: 'Premium Tatkal (PT)',
  LD: 'Ladies (LD)',
  DF: 'Defence (DF)',
  SS: 'Senior Citizen (SS)',
  HP: 'Handicapped (HP)',
  PH: 'Physically Handicapped (PH)',
  YU: 'Youth (YU)',
  DU: 'Duty (DU)',
} as const;

export type ClassCode = keyof typeof CLASS_CODES;
export type QuotaCode = keyof typeof QUOTA_CODES;

/** Mirrors MAX_PASSENGERS_PER_REQUEST on the server. */
export const MAX_PASSENGERS = 6;
