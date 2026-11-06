import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ApiFailure,
  executeExport,
  fetchBatches,
  fetchLatestRehearsal,
  fetchOperatorStatus,
  inspectBatch,
  inspectLineage,
  previewExport,
  reconcileExport,
  reviewSubmission,
  runRehearsal,
  seedSyntheticBatch,
  withdrawSubmission,
} from '@/lib/api';

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

describe('Operator API Client', () => {
  it('fetchOperatorStatus returns status on success', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, {
        operator_enabled: true,
        workspace_root: '/tmp/operator',
        batches_count: 2,
        total_submissions: 16,
        total_pending_review: 4,
        total_approved: 10,
        total_withdrawn: 2,
        latest_rehearsal_passed: true,
        is_synthetic_environment: true,
      }),
    );

    const res = await fetchOperatorStatus();
    expect(res.operator_enabled).toBe(true);
    expect(res.batches_count).toBe(2);
  });

  it('fetchOperatorStatus raises ApiFailure with 403 when operator mode is disabled', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(403, {
        error: 'Operator mode is disabled. To enable locally, set RAILCONFIRM_OPERATOR_ENABLED=true.',
        details: [{ code: 'OPERATOR_DISABLED', message: 'Operator mode is disabled.' }],
        request_id: 'req_123',
      }),
    );

    await expect(fetchOperatorStatus()).rejects.toThrow(ApiFailure);
  });

  it('fetchBatches and seedSyntheticBatch call expected routes', async () => {
    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, { batches: [{ batch_id: 'B1', total_submissions: 5 }], count: 1 }),
    );
    const listRes = await fetchBatches();
    expect(listRes.count).toBe(1);

    fetchMock().mockResolvedValueOnce(
      jsonResponse(201, { batch_id: 'SYNTHETIC_001', total_submissions: 8 }),
    );
    const seedRes = await seedSyntheticBatch();
    expect(seedRes.batch_id).toBe('SYNTHETIC_001');
  });

  it('inspectBatch retrieves batch inspection with PII scan and audit', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, {
        summary: { batch_id: 'B1' },
        pii_scan: { passed: true, findings_count: 0, findings: [] },
        audit_report: { total_submissions: 8 },
        submissions: [],
        withdrawal_log: [],
      }),
    );

    const res = await inspectBatch('B1');
    expect(res.summary.batch_id).toBe('B1');
    expect(res.pii_scan.passed).toBe(true);
  });

  it('reviewSubmission sends review action and rationale', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, { submission_id: 'S1', action: 'approved' }),
    );

    await reviewSubmission('B1', 'S1', 'approved', 'reviewer1', 'verified clean');
    const [url, init] = fetchMock().mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/v1/operator/batches/B1/review');
    expect(JSON.parse(String(init.body))).toEqual({
      submission_id: 'S1',
      action: 'approved',
      reviewer: 'reviewer1',
      rationale: 'verified clean',
    });
  });

  it('withdrawSubmission sends withdrawal reason and operator', async () => {
    fetchMock().mockResolvedValue(
      jsonResponse(200, { submission_id: 'S1', reason: 'consent withdrawn' }),
    );

    await withdrawSubmission('B1', 'S1', 'consent withdrawn', 'operator1');
    const [url, init] = fetchMock().mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain('/v1/operator/batches/B1/withdraw');
    expect(JSON.parse(String(init.body))).toEqual({
      submission_id: 'S1',
      reason: 'consent withdrawn',
      operator: 'operator1',
    });
  });

  it('previewExport and executeExport call corresponding endpoints', async () => {
    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, { batch_id: 'B1', approved_count: 2 }),
    );
    const prev = await previewExport('B1');
    expect(prev.approved_count).toBe(2);

    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, { batch_id: 'B1', lineage_status: 'verified_in_sync' }),
    );
    await executeExport('B1', 'DATASET_CUSTOM');
    const [url, init] = fetchMock().mock.calls[1] as unknown as [string, RequestInit];
    expect(url).toContain('/v1/operator/batches/B1/export');
    expect(JSON.parse(String(init.body))).toEqual({ dataset_id: 'DATASET_CUSTOM' });
  });

  it('inspectLineage and reconcileExport manage lineage status', async () => {
    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, { batch_id: 'B1', is_synced: false, status: 'stale_withdrawn_records_present' }),
    );
    const lin = await inspectLineage('B1');
    expect(lin.is_synced).toBe(false);

    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, { batch_id: 'B1', reconciled_booking_groups: 1 }),
    );
    await reconcileExport('B1');
    expect(fetchMock().mock.calls[1][0]).toContain('/v1/operator/batches/B1/reconcile');
  });

  it('runRehearsal executes rehearsal and fetchLatestRehearsal returns null on 404', async () => {
    fetchMock().mockResolvedValueOnce(
      jsonResponse(200, {
        report: { software_rehearsal_passed: true, gate_count: 15 },
        summary_text: 'ALL GATES PASSED',
      }),
    );
    const runRes = await runRehearsal();
    expect(runRes.report.software_rehearsal_passed).toBe(true);

    // 404 from latest returns null without throwing
    fetchMock().mockResolvedValueOnce(
      jsonResponse(404, {
        error: 'No prior rehearsal report exists.',
        details: [{ code: 'REHEARSAL_NOT_FOUND', message: 'Not found' }],
      }),
    );
    const latest = await fetchLatestRehearsal();
    expect(latest).toBeNull();
  });
});

