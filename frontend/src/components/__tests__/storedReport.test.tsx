/**
 * Reopening a stored report.
 *
 * A saved prediction is the one part of this product that outlives the page, so the
 * failure copy has to be exact: "not found" can mean it was never kept, that retention
 * closed, or that this server keeps nothing at all, and the backend's code says which.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StoredPredictionReport } from '@/components/prediction/StoredPredictionReport';
import { configuredApiUrl } from '@/lib/api';
import type { PredictionResponse } from '@/lib/types';

const push = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, prefetch: vi.fn(), refresh: vi.fn() }),
}));

const ID = 'a1b2c3d4-0000-0000-0000-000000000009';

const report: PredictionResponse = {
  prediction_id: ID,
  target: 'final_chart_cnf',
  target_definition: 'Probability of each final-chart outcome for each passenger.',
  prediction_at: '2026-12-10T08:00:00+05:30',
  created_at: '2026-12-10T02:30:00Z',
  model_version: 'fixture_v1',
  registry_status: 'ready',
  feature_schema_version: '2.0.0',
  evidence_coverage: 'insufficient',
  is_supported: false,
  passenger_count: 1,
  passenger_outcomes: [],
  group_outcome: null,
  limitations: ['RailConfirm is an independent research tool and not an official IRCTC service.'],
  warnings: [],
  outcome_classes: 'CNF, RAC, WL, CANCELLED, OTHER.',
  stored: true,
  report_url: `/v1/predictions/${ID}`,
  retention_expires_at: '2026-12-17T02:30:00Z',
};

function jsonResponse(status: number, body: unknown, requestId = 'req-1') {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': requestId },
  });
}

const fetchMock = () => vi.mocked(fetch);

beforeEach(() => {
  push.mockClear();
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('StoredPredictionReport', () => {
  it('fetches by the id in the path and renders the report as stored', async () => {
    fetchMock().mockResolvedValue(jsonResponse(200, report));
    render(<StoredPredictionReport predictionId={ID} />);

    await waitFor(() => expect(screen.getByText('Prediction report')).toBeInTheDocument());
    const [url] = fetchMock().mock.calls[0] as unknown as [string];
    expect(url).toBe(`${configuredApiUrl()}/v1/predictions/${ID}`);
    // The copy must say the numbers were not recomputed on open.
    expect(document.body.textContent).toContain('as it was served');
    expect(document.body.textContent).toContain('fixture_v1');
  });

  it('percent-encodes the id so it cannot address another path', async () => {
    fetchMock().mockResolvedValue(jsonResponse(404, { error: 'no', details: [] }));
    render(<StoredPredictionReport predictionId={'../../other'} />);
    await waitFor(() => expect(fetchMock()).toHaveBeenCalled());
    const [url] = fetchMock().mock.calls[0] as unknown as [string];
    // The separators are encoded, so the request stays under /v1/predictions/.
    expect(url).toBe(`${configuredApiUrl()}/v1/predictions/..%2F..%2Fother`);
  });

  it('explains an aged-out or never-stored id without pretending to know which', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(404, {
        error: 'No stored report has this id.',
        details: [{ code: 'not_found', message: 'No stored report has this id.' }],
        request_id: 'req-404',
      }),
    );
    render(<StoredPredictionReport predictionId={ID} />);

    await waitFor(() => expect(screen.getByText('Report not available')).toBeInTheDocument());
    expect(document.body.textContent).toContain('retention window has closed');
    expect(screen.getByText('Request id: req-404')).toBeInTheDocument();
  });

  it('says plainly when this server keeps no history at all', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(404, {
        error: 'This server keeps no prediction history.',
        details: [{ code: 'history_disabled', message: 'This server keeps no prediction history.' }],
        request_id: 'req-off',
      }),
    );
    render(<StoredPredictionReport predictionId={ID} />);

    await waitFor(() => expect(screen.getByText('Report not available')).toBeInTheDocument());
    expect(document.body.textContent).toContain('keeps no prediction history');
    expect(document.body.textContent).not.toContain('retention window has closed');
  });

  it('reports a transport failure as one, not as an absent report', async () => {
    fetchMock().mockRejectedValue(new TypeError('fetch failed'));
    render(<StoredPredictionReport predictionId={ID} />);

    await waitFor(() => expect(screen.getByText('Report not available')).toBeInTheDocument());
    expect(document.body.textContent).toContain('did not complete');
  });

  it('re-fetches when the user asks to try again', async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(500, { error: 'boom', details: [], request_id: 'r' }))
      .mockResolvedValueOnce(jsonResponse(200, report));
    render(<StoredPredictionReport predictionId={ID} />);

    await waitFor(() => expect(screen.getByText('Report not available')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByText('Prediction report')).toBeInTheDocument());
    expect(fetchMock()).toHaveBeenCalledTimes(2);
  });

  it('offers a way back to a new estimate', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(404, {
        error: 'No stored report has this id.',
        details: [{ code: 'not_found', message: 'No stored report has this id.' }],
        request_id: 'req-x',
      }),
    );
    render(<StoredPredictionReport predictionId={ID} />);
    await waitFor(() => expect(screen.getByText('Report not available')).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: 'Start a new estimate' }));
    expect(push).toHaveBeenCalledWith('/');
  });

  it('asks before deleting, then removes only after the backend agrees', async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(200, report))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(<StoredPredictionReport predictionId={ID} />);
    await waitFor(() => expect(screen.getByText('Prediction report')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Delete this report' }));
    // The first click only asks.
    expect(fetchMock()).toHaveBeenCalledTimes(1);

    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));
    await waitFor(() => expect(screen.getByText('Report deleted')).toBeInTheDocument());
    const [url, init] = fetchMock().mock.calls[1] as unknown as [string, RequestInit];
    expect(init.method).toBe('DELETE');
    expect(url).toBe(`${configuredApiUrl()}/v1/predictions/${ID}`);
    expect(screen.getByRole('link', { name: 'See what is still kept' })).toHaveAttribute(
      'href',
      '/history',
    );
  });

  it('keeps showing the report when the delete is refused', async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(200, report))
      .mockResolvedValueOnce(
        jsonResponse(404, {
          error: 'No stored report with this id could be deleted.',
          details: [
            { code: 'not_found', message: 'No stored report with this id could be deleted.' },
          ],
          request_id: 'req-gone',
        }),
      );
    render(<StoredPredictionReport predictionId={ID} />);
    await waitFor(() => expect(screen.getByText('Prediction report')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Delete this report' }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(screen.getByText(/Not deleted: No stored report/)).toBeInTheDocument());
    // The report is still on screen: a delete that did not happen must not look done.
    expect(screen.getByText('Prediction report')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete this report' })).toBeInTheDocument();
  });

  it('reports a network failure during deletion without claiming success', async () => {
    fetchMock().mockResolvedValueOnce(jsonResponse(200, report));
    fetchMock().mockRejectedValueOnce(new TypeError('fetch failed'));
    render(<StoredPredictionReport predictionId={ID} />);
    await waitFor(() => expect(screen.getByText('Prediction report')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Delete this report' }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(screen.getByText(/Not deleted/)).toBeInTheDocument());
    expect(screen.getByText('Prediction report')).toBeInTheDocument();
  });
});
