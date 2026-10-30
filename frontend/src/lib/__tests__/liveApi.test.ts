/**
 * Live cross-stack contract tests: the real client, a real server, nothing mocked.
 *
 * `npm test` must pass with no backend running, so this file is excluded from that
 * run entirely. `npm run test:live` is the opt-in command, and
 * `scripts/smoke_full_stack.py` starts the server and runs it — that is what
 * `.github/workflows/ci.yml` does, so these tests cannot rot into permanent skips
 * that nobody notices. `vitest.live.config.ts` refuses to start without
 * `RAILCONFIRM_LIVE_API_URL`, and the check below repeats the refusal here: a suite
 * that quietly skips itself is indistinguishable from a suite that passes.
 *
 * What they prove: the request this client builds is accepted by the server, the
 * response is the shape `types.ts` declares, and the abstention/history behaviour the
 * UI renders is the behaviour the server actually produces. What they do not prove:
 * anything about railway prediction accuracy, or how a human uses the page — that
 * needs a browser, which is still not configured.
 */
import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import {
  ApiFailure,
  checkHealth,
  deleteStoredPrediction,
  fetchStoredPrediction,
  fetchStoredReports,
  submitPrediction,
} from '@/lib/api';
import type { PredictionRequest } from '@/lib/types';

const LIVE_URL = process.env.RAILCONFIRM_LIVE_API_URL ?? '';
if (!LIVE_URL) {
  throw new Error(
    'This suite drives a real backend. Set RAILCONFIRM_LIVE_API_URL (npm run test:live ' +
      'reads it) rather than running the file directly.',
  );
}

/** Journey far enough ahead that the one-clear-day horizon rule is satisfied. */
function booking(overrides: Partial<PredictionRequest> = {}): PredictionRequest {
  const journeyDate = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);
  const observedAt = new Date(Date.now() - 60 * 60 * 1000);
  return {
    journey: {
      train_number: '12301',
      journey_date: journeyDate.toISOString().slice(0, 10),
      boarding_station: 'NDLS',
      destination_station: 'HWH',
      class_code: 'SL',
      quota_code: 'GN',
    },
    prediction_at: new Date().toISOString(),
    passengers: [
      {
        original_status: 'GNWL/45',
        current_status: 'GNWL/12',
        current_status_observed_at: observedAt.toISOString(),
      },
      { original_status: 'GNWL/46', current_status: 'RAC 3' },
    ],
    ...overrides,
  };
}

const storedIds: string[] = [];

describe('the client against a running backend', () => {
  beforeAll(() => {
    // `resolveApiBase()` reads this per request, so the live server is addressed the
    // same way the browser would address it.
    process.env.NEXT_PUBLIC_API_URL = LIVE_URL;
  });

  afterAll(async () => {
    for (const id of storedIds) {
      await deleteStoredPrediction(id).catch(() => undefined);
    }
  });

  it('reports a server with no promoted model', async () => {
    const health = await checkHealth();
    expect(health.status).toBe('ok');
    expect(health.model_available).toBe(false);
    expect(health.model_version).toBe('no_model_v0');
    expect(health.registry_status).toBe('no_active_version');
    expect(health.prediction_history?.enabled).toBe(true);
  });

  it('receives a structured abstention rather than an invented probability', async () => {
    const report = await submitPrediction(booking());

    expect(report.passenger_count).toBe(2);
    expect(report.evidence_coverage).toBe('insufficient');
    expect(report.is_supported).toBe(false);
    expect(report.stored).toBe(false);
    expect(report.report_url).toBeNull();

    for (const outcome of report.passenger_outcomes) {
      expect(outcome.is_supported).toBe(false);
      expect(outcome.abstention_reason).toBe('no_trained_model');
      // An abstention carries no number at all. Zero would be a different claim.
      expect(outcome.p_cnf).toBeNull();
      expect(outcome.basis).toBeNull();
    }

    // The booking's joint outcomes are reported as one dependent group, and it abstains
    // for the same reason the passengers do.
    expect(report.group_outcome).not.toBeNull();
    expect(report.group_outcome?.is_supported).toBe(false);
    expect(report.group_outcome?.abstention_reason).toBe('no_trained_model');
    expect(report.limitations.some((text) => text.includes('no_active_version'))).toBe(true);
  });

  it('stores, reopens and deletes one report by its internal id', async () => {
    const report = await submitPrediction(booking({ persist: true }));
    expect(report.stored).toBe(true);
    expect(report.report_url).toBe(`/v1/predictions/${report.prediction_id}`);
    expect(report.retention_expires_at).not.toBeNull();
    storedIds.push(report.prediction_id);

    const reopened = await fetchStoredPrediction(report.prediction_id);
    expect(reopened.prediction_id).toBe(report.prediction_id);
    expect(reopened.target).toBe(report.target);
    expect(reopened.stored).toBe(true);

    const listed = await fetchStoredReports();
    const ids = listed.reports.map((entry) => entry.prediction_id);
    expect(ids).toContain(report.prediction_id);
    expect(listed.count).toBe(listed.reports.length);
    // The list describes what is kept without describing the ticket.
    const summary = listed.reports.find((entry) => entry.prediction_id === report.prediction_id);
    expect(Object.keys(summary ?? {}).sort()).toEqual([
      'model_version',
      'prediction_id',
      'recorded_at',
      'retention_expires_at',
      'target',
    ]);

    await deleteStoredPrediction(report.prediction_id);

    await expect(fetchStoredPrediction(report.prediction_id)).rejects.toMatchObject({
      kind: 'http',
      status: 404,
      code: 'not_found',
    });
  });

  it('surfaces a field-level refusal with the field the server named', async () => {
    const invalid = booking();
    invalid.journey = { ...invalid.journey, train_number: '12' };

    const failure = await submitPrediction(invalid).then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(ApiFailure);
    const apiFailure = failure as ApiFailure;
    expect(apiFailure.kind).toBe('validation');
    expect(apiFailure.status).toBe(422);
    expect(apiFailure.fieldErrors['journey.train_number']).toBeTruthy();
    expect(apiFailure.requestId).toBeTruthy();
  });

  it('refuses a prediction timestamp inside the eligible horizon', async () => {
    const insideHorizon = booking();
    insideHorizon.prediction_at = `${insideHorizon.journey.journey_date}T00:00:00+05:30`;

    const failure = await submitPrediction(insideHorizon).then(
      () => null,
      (error: unknown) => error,
    );

    expect(failure).toBeInstanceOf(ApiFailure);
    expect((failure as ApiFailure).status).toBe(422);
    expect((failure as ApiFailure).code).toBe('INVALID_PREDICTION_AT');
  });
});
