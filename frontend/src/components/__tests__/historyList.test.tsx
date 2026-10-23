/**
 * The history list and the deletion it offers.
 *
 * Two properties matter more than the layout: the page must distinguish "nothing is kept"
 * from "this server keeps nothing", because those lead the user to different actions; and a
 * delete that has not happened must never look like one that has.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HistoryList } from '@/components/prediction/HistoryList';
import { configuredApiUrl } from '@/lib/api';

const KEEPING = [
  {
    prediction_id: '11111111-0000-4000-8000-000000000001',
    target: 'final_chart_cnf',
    model_version: 'fixture_v1',
    recorded_at: '2026-10-21T09:00:00Z',
    retention_expires_at: '2026-10-28T09:00:00Z',
  },
  {
    prediction_id: '22222222-0000-4000-8000-000000000002',
    target: 'final_chart_cnf_or_rac',
    model_version: 'fixture_v2',
    recorded_at: '2026-10-22T09:00:00Z',
    retention_expires_at: '2026-10-29T09:00:00Z',
  },
];

function jsonResponse(status: number, body: unknown, requestId = 'req-1') {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'X-Request-ID': requestId },
  });
}

function listResponse(reports = KEEPING) {
  return jsonResponse(200, { reports, count: reports.length, retention_days: 7 });
}

const fetchMock = () => vi.mocked(fetch);

function methodOf(call: unknown[]): string {
  return (call[1] as RequestInit).method ?? 'GET';
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('HistoryList', () => {
  it('lists each kept report with its clocks and provenance', async () => {
    fetchMock().mockResolvedValue(listResponse());
    render(<HistoryList />);

    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());
    const rows = screen.getAllByRole('link', { name: /Report / });
    expect(rows).toHaveLength(2);
    expect(document.body.textContent).toContain('fixture_v1');
    expect(document.body.textContent).toContain('retrievable until 2026-10-28T09:00:00Z');
    expect(fetchMock()).toHaveBeenCalledTimes(1);
    const [url] = fetchMock().mock.calls[0] as unknown as [string];
    expect(url).toBe(`${configuredApiUrl()}/v1/predictions`);
  });

  it('links a row to the reopen route using the full internal id', async () => {
    fetchMock().mockResolvedValue(listResponse([KEEPING[0]]));
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('1 kept report on this server.')).toBeInTheDocument());
    const link = screen.getByRole('link', { name: /Report 11111111/ });
    expect(link).toHaveAttribute('href', `/prediction/${KEEPING[0].prediction_id}`);
  });

  it('says the list holds no ticket detail, because that is what the backend returns', async () => {
    fetchMock().mockResolvedValue(listResponse());
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());
    expect(document.body.textContent).toContain('no journey, no statuses and no probabilities');
  });

  it('distinguishes an empty history from a disabled one', async () => {
    fetchMock().mockResolvedValue(listResponse([]));
    const { unmount } = render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('Nothing is being kept')).toBeInTheDocument());
    expect(document.body.textContent).not.toContain('keeps no history');
    unmount();

    fetchMock().mockResolvedValue(
      jsonResponse(404, {
        error: 'This server keeps no prediction history.',
        details: [
          { code: 'history_disabled', message: 'This server keeps no prediction history.' },
        ],
        request_id: 'req-off',
      }),
    );
    render(<HistoryList />);
    await waitFor(() =>
      expect(screen.getByText('This server keeps no history')).toBeInTheDocument(),
    );
    expect(document.body.textContent).not.toContain('Nothing is being kept');
  });

  it('offers a retry when the list cannot be read, and refetches on it', async () => {
    fetchMock()
      .mockResolvedValueOnce(jsonResponse(500, { error: 'boom', details: [], request_id: 'r-5' }))
      .mockResolvedValueOnce(listResponse());
    render(<HistoryList />);

    await waitFor(() => expect(screen.getByText('The history could not be read')).toBeInTheDocument());
    expect(screen.getByText('Request id: r-5')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());
    expect(fetchMock()).toHaveBeenCalledTimes(2);
  });

  it('classifies a transport failure as one', async () => {
    fetchMock().mockRejectedValue(new TypeError('fetch failed'));
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('The history could not be read')).toBeInTheDocument());
    expect(document.body.textContent).toContain('did not complete');
  });

  it('requires a second click before anything is deleted', async () => {
    fetchMock().mockResolvedValue(listResponse());
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());

    await userEvent.click(screen.getAllByRole('button', { name: 'Delete report' })[0]);
    // Only the list has been fetched so far: the first click asks, it does not remove.
    expect(fetchMock()).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Confirm delete' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Keep it' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Keep it' }));
    expect(screen.queryByRole('button', { name: 'Confirm delete' })).not.toBeInTheDocument();
    expect(fetchMock()).toHaveBeenCalledTimes(1);
  });

  it('removes the row only after the backend confirms the delete', async () => {
    fetchMock()
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());

    await userEvent.click(screen.getAllByRole('button', { name: 'Delete report' })[0]);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(screen.getByText('1 kept report on this server.')).toBeInTheDocument());
    const deleteCall = fetchMock().mock.calls[1] as unknown as [string, RequestInit];
    expect(deleteCall[1].method).toBe('DELETE');
    expect(deleteCall[0]).toContain(`/v1/predictions/${KEEPING[0].prediction_id}`);
    expect(screen.getByRole('status')).toHaveTextContent('Removed');
    expect(screen.queryByRole('link', { name: /Report 11111111/ })).not.toBeInTheDocument();
  });

  it('keeps the row listed when the delete is refused', async () => {
    fetchMock()
      .mockResolvedValueOnce(listResponse())
      .mockResolvedValueOnce(
        jsonResponse(404, {
          error: 'No stored report with this id could be deleted.',
          details: [
            { code: 'not_found', message: 'No stored report with this id could be deleted.' },
          ],
          request_id: 'req-gone',
        }),
      );
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());

    await userEvent.click(screen.getAllByRole('button', { name: 'Delete report' })[0]);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() =>
      expect(screen.getByText(/Not deleted: No stored report with this id/)).toBeInTheDocument(),
    );
    expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument();
    const row = screen.getByRole('link', { name: /Report 11111111/ }).closest('li');
    expect(within(row as HTMLElement).getByRole('button', { name: 'Delete report' })).toBeInTheDocument();
  });

  it('reports a network failure during deletion without pretending it worked', async () => {
    fetchMock().mockResolvedValueOnce(listResponse());
    fetchMock().mockRejectedValueOnce(new TypeError('fetch failed'));
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument());

    await userEvent.click(screen.getAllByRole('button', { name: 'Delete report' })[0]);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Not deleted'));
    expect(screen.getByText('2 kept reports on this server.')).toBeInTheDocument();
  });

  it('counts removals in the empty state so a cleared list is not read as never-used', async () => {
    fetchMock()
      .mockResolvedValueOnce(listResponse([KEEPING[0]]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    render(<HistoryList />);
    await waitFor(() => expect(screen.getByText('1 kept report on this server.')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: 'Delete report' }));
    await userEvent.click(screen.getByRole('button', { name: 'Confirm delete' }));

    await waitFor(() => expect(screen.getByText('Nothing is being kept')).toBeInTheDocument());
    expect(screen.getByText('1 report removed in this session.')).toBeInTheDocument();
  });
});
