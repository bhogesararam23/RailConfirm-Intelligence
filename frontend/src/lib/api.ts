import type { PredictionRequest, PredictionResponse, APIErrorShape } from './types';

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Typed API error — carries HTTP status and structured error code from the server.
 */
export class APIError extends Error {
  constructor(
    message: string,
    public readonly code: string,
    public readonly httpStatus: number,
    public readonly detail?: string,
  ) {
    super(message);
    this.name = 'APIError';
  }
}

/**
 * Submit a manual prediction request to the backend.
 * Throws APIError on non-2xx responses; throws Error for network failures.
 */
export async function submitPrediction(
  request: PredictionRequest,
): Promise<PredictionResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/v1/predictions/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
  } catch (networkError) {
    throw new Error(
      'Could not reach the backend. Please check that the backend is running.',
    );
  }

  if (!response.ok) {
    let errorBody: APIErrorShape = {
      error: 'Request failed',
      code: 'FETCH_ERROR',
    };
    try {
      errorBody = (await response.json()) as APIErrorShape;
    } catch {
      // JSON parse failed; use defaults above
    }
    throw new APIError(
      errorBody.error || 'Request failed',
      errorBody.code || 'UNKNOWN',
      response.status,
      errorBody.detail,
    );
  }

  return response.json() as Promise<PredictionResponse>;
}

/**
 * Health-check the backend.
 * Returns status/model/data version strings; throws if unavailable.
 */
export async function checkHealth(): Promise<{
  status: string;
  model_version: string;
  data_version: string;
}> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/v1/health`);
  } catch {
    throw new Error('Backend unavailable');
  }
  if (!response.ok) throw new Error('Backend unavailable');
  return response.json() as Promise<{
    status: string;
    model_version: string;
    data_version: string;
  }>;
}
