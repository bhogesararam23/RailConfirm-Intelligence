import type {
  ApiErrorBody,
  ErrorDetail,
  HealthResponse,
  PredictionRequest,
  PredictionResponse,
} from './types';

const DEFAULT_API_URL = 'http://127.0.0.1:8000';

/** Request timeout. A hung backend must not leave the form spinning forever. */
export const REQUEST_TIMEOUT_MS = 15000;

function resolveApiBase(): string {
  return (process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL).replace(/\/+$/, '');
}

/**
 * A failure the user can be told something specific about.
 *
 * `fieldErrors` carries the server's per-field messages so the form can mark the
 * offending input instead of showing one generic red banner.
 */
export class ApiFailure extends Error {
  readonly kind: 'validation' | 'http' | 'network' | 'timeout' | 'config';
  readonly status: number | null;
  readonly code: string | null;
  readonly requestId: string | null;
  readonly fieldErrors: Record<string, string>;

  constructor(options: {
    message: string;
    kind: ApiFailure['kind'];
    status?: number | null;
    code?: string | null;
    requestId?: string | null;
    fieldErrors?: Record<string, string>;
  }) {
    super(options.message);
    this.name = 'ApiFailure';
    this.kind = options.kind;
    this.status = options.status ?? null;
    this.code = options.code ?? null;
    this.requestId = options.requestId ?? null;
    this.fieldErrors = options.fieldErrors ?? {};
  }
}

/**
 * A TypeError from fetch() means the request never completed: the backend is down,
 * the origin is not in its CORS allowlist, or the configured URL is wrong. Browsers
 * hide the reason for privacy, so the message names all three instead of guessing.
 */
function networkFailure(url: string): ApiFailure {
  return new ApiFailure({
    kind: 'network',
    message:
      `The request to ${url} did not complete. The backend may not be running, ` +
      'this page\u2019s origin may not be allowed by its CORS configuration, or the ' +
      'configured API URL is wrong.',
  });
}

function parseFieldErrors(body: ApiErrorBody): Record<string, string> {
  const byField: Record<string, string> = {};
  for (const detail of body.details ?? []) {
    if (detail.field) {
      byField[detail.field] = detail.message;
    }
  }
  return byField;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ApiErrorBody).error === 'string' &&
    Array.isArray((value as ApiErrorBody).details)
  );
}

async function requestJson<T>(
  path: string,
  init: RequestInit,
  timeoutMs: number,
): Promise<T> {
  const base = resolveApiBase();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { ...init, signal: controller.signal });
  } catch (error) {
    // An aborted fetch rejects with a DOMException in browsers and a plain Error in
    // jsdom, so the name is what identifies it.
    if (error instanceof Error && error.name === 'AbortError') {
      throw new ApiFailure({
        kind: 'timeout',
        message: `The backend did not answer within ${Math.round(timeoutMs / 1000)} seconds.`,
      });
    }
    throw networkFailure(base);
  } finally {
    clearTimeout(timer);
  }

  const requestId = response.headers.get('X-Request-ID');

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiFailure({
      kind: 'http',
      status: response.status,
      requestId,
      message:
        response.status >= 500
          ? 'The backend returned an error it did not describe.'
          : 'The backend replied, but not with the JSON this client expects.',
    });
  }

  if (!response.ok) {
    const body: ApiErrorBody = isApiErrorBody(payload)
      ? (payload as ApiErrorBody)
      : {
          error:
            typeof (payload as { detail?: unknown })?.detail === 'string'
              ? (payload as { detail: string }).detail
              : `Request failed with status ${response.status}.`,
          details: [] as ErrorDetail[],
          request_id: requestId,
        };
    throw new ApiFailure({
      kind: response.status === 422 ? 'validation' : 'http',
      status: response.status,
      code: body.details[0]?.code ?? null,
      requestId: body.request_id ?? requestId,
      fieldErrors: parseFieldErrors(body),
      message: body.error,
    });
  }

  return payload as T;
}

export function submitPrediction(
  request: PredictionRequest,
  timeoutMs = REQUEST_TIMEOUT_MS,
  signal?: AbortSignal,
): Promise<PredictionResponse> {
  const init: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  };
  if (signal) {
    // Chain the caller's abort into the internal timeout.
    const chained = new AbortController();
    const forward = () => chained.abort();
    signal.addEventListener('abort', forward, { once: true });
    init.signal = chained.signal;
  }
  return requestJson<PredictionResponse>('/v1/predictions/manual', init, timeoutMs);
}

export function checkHealth(timeoutMs = REQUEST_TIMEOUT_MS): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/v1/health', { method: 'GET' }, timeoutMs);
}

/** The origin this client will call, for display and for the privacy statement. */
export function configuredApiUrl(): string {
  return resolveApiBase();
}

/**
 * The local-only claim is true only while the API points at a loopback address.
 * Anything else sends the request off this machine, and the copy must say so.
 */
export function isLoopbackApi(url = configuredApiUrl()): boolean {
  try {
    const { hostname } = new URL(url);
    return (
      hostname === 'localhost' ||
      hostname === '127.0.0.1' ||
      hostname === '[::1]' ||
      hostname === '::1'
    );
  } catch {
    return false;
  }
}
