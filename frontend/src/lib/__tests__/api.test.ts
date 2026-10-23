import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiFailure, checkHealth, configuredApiUrl, isLoopbackApi, submitPrediction } from '@/lib/api';
import type { PredictionRequest } from '@/lib/types';

const request: PredictionRequest = {
  journey: {
    train_number: '12301',
    journey_date: '2026-12-20',
    boarding_station: 'NDLS',
    destination_station: 'HWH',
    class_code: 'SL',
    quota_code: 'GN',
  },
  prediction_at: '2026-12-10T08:00:00+05:30',
  passengers: [{ original_status: 'GNWL/45', current_status: 'GNWL/12' }],
};

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const fetchMock = () => vi.mocked(fetch);

describe('submitPrediction', () => {
  it('returns the parsed response on success', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, { prediction_id: 'p1', evidence_coverage: 'insufficient' }),
    );
    await expect(submitPrediction(request)).resolves.toMatchObject({ prediction_id: 'p1' });
  });

  it('sends the offset-aware timestamp and the declared target', async () => {
    fetchMock().mockResolvedValue(jsonResponse(200, {}));
    await submitPrediction(request);
    const [, init] = fetchMock().mock.calls[0] as unknown as [string, RequestInit];
    expect(JSON.parse(String(init.body)).prediction_at).toBe('2026-12-10T08:00:00+05:30');
  });

  it('reads the documented error envelope on a 422', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(
        422,
        {
          error: 'Request validation failed.',
          details: [
            {
              code: 'VALIDATION_ERROR',
              message: 'prediction_at has no timezone offset',
              field: 'prediction_at',
            },
          ],
          request_id: 'trace-1',
        },
        { 'X-Request-ID': 'trace-1' },
      ),
    );

    const failure = await submitPrediction(request).catch((error) => error);
    expect(failure).toBeInstanceOf(ApiFailure);
    expect(failure.kind).toBe('validation');
    expect(failure.status).toBe(422);
    expect(failure.code).toBe('VALIDATION_ERROR');
    expect(failure.requestId).toBe('trace-1');
    expect(failure.fieldErrors).toEqual({ prediction_at: 'prediction_at has no timezone offset' });
  });

  it('classifies a transport failure as network and names the CORS possibility', async () => {
    fetchMock().mockRejectedValue(new TypeError('Failed to fetch'));
    const failure = await submitPrediction(request).catch((error) => error);
    expect(failure).toBeInstanceOf(ApiFailure);
    expect(failure.kind).toBe('network');
    // The old message asserted the backend was not running. A blocked CORS preflight
    // looks identical from the page, and that was the actual failure here.
    expect(failure.message).toMatch(/CORS|not allowed/);
  });

  it('reports a timeout rather than spinning forever', async () => {
    fetchMock().mockImplementation(
      (_input: unknown, init?: RequestInit) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener('abort', () => {
            reject(
              Object.assign(new Error('aborted'), { name: 'AbortError' }) as unknown as Error,
            );
          });
        }),
    );
    const failure = await submitPrediction(request, 1).catch((error) => error);
    expect(failure.kind).toBe('timeout');
  });

  it('does not claim JSON when the reply is not JSON', async () => {
    fetchMock().mockResolvedValue(new Response('<html>500</html>', { status: 500 }));
    const failure = await submitPrediction(request).catch((error) => error);
    expect(failure.kind).toBe('http');
    expect(failure.message).toMatch(/did not describe|not with the JSON/);
  });
});

describe('checkHealth', () => {
  it('returns model availability, not just liveness', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, {
        status: 'ok',
        model_version: 'no_model_v0',
        data_version: 'none',
        app_version: '0.1.0',
        model_available: false,
        registry_status: 'no_active_version',
        limits: {},
      }),
    );
    await expect(checkHealth()).resolves.toMatchObject({ model_available: false });
  });
});

describe('isLoopbackApi', () => {
  it.each([
    ['http://127.0.0.1:8000', true],
    ['http://localhost:8000', true],
    ['http://example.com', false],
    ['not-a-url', false],
  ])('%s → local only %s', (url, expected) => {
    expect(isLoopbackApi(url)).toBe(expected);
  });

  it('strips a trailing slash from the configured base', () => {
    expect(configuredApiUrl().endsWith('/')).toBe(false);
  });
});
