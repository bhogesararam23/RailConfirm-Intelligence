import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { OperatorBanner } from '@/components/operator/OperatorBanner';
import { OperatorOverview } from '@/components/operator/OperatorOverview';
import { BatchAuditView } from '@/components/operator/BatchAuditView';
import { SubmissionReviewView } from '@/components/operator/SubmissionReviewView';
import { WithdrawalLineageView } from '@/components/operator/WithdrawalLineageView';
import { RehearsalView } from '@/components/operator/RehearsalView';
import type { BatchInspection, BatchSummary, OperatorStatus, RehearsalReportData } from '@/lib/types';

const mockStatus: OperatorStatus = {
  operator_enabled: true,
  workspace_root: '/local/data/operator',
  batches_count: 1,
  total_submissions: 8,
  total_pending_review: 6,
  total_approved: 2,
  total_withdrawn: 0,
  latest_rehearsal_passed: true,
  is_synthetic_environment: true,
};

const mockBatchSummary: BatchSummary = {
  batch_id: 'BATCH_TEST_001',
  file_path: '/path/to/BATCH_TEST_001.json',
  schema_version: '1.0.0',
  created_at: '2026-05-01T12:00:00Z',
  total_submissions: 8,
  approved_count: 2,
  rejected_count: 0,
  quarantined_count: 0,
  pending_count: 6,
  withdrawn_count: 0,
  canonical_sha256: 'deadbeef1234567890abcdef',
};

const mockInspection: BatchInspection = {
  summary: mockBatchSummary,
  pii_scan: {
    passed: true,
    findings_count: 0,
    findings: [],
  },
  audit_report: {
    batch_id: 'BATCH_TEST_001',
    total_submissions: 8,
    total_passengers: 8,
    unique_trains: ['12951', '12952'],
    unique_journey_dates: ['2026-06-01', '2026-06-02'],
    class_distribution: { SL: 8 },
    quota_distribution: { GN: 8 },
    quality_warnings: [],
    structural_errors: [],
    is_technically_eligible: true,
    is_scientifically_adequate: false,
    is_model_training_approved: false,
  },
  submissions: [
    {
      submission_id: 'SUB_001',
      pseudonym_group_id: 'anon_grp_001',
      train_number: '12951',
      journey_date: '2026-06-01',
      boarding_station: 'NDLS',
      destination_station: 'MMCT',
      class_code: 'SL',
      quota_code: 'GN',
      scheduled_departure_at: '2026-06-01T16:30:00Z',
      review_status: 'pending_review',
      review_notes: null,
      reviewed_by: null,
      reviewed_at: null,
      passengers: [
        {
          passenger_sequence: 1,
          original_status_raw: 'GNWL 25',
          original_status_category: 'WL',
          original_status_position: 25,
          outcome: {
            outcome_status_raw: 'CNF',
            outcome_category: 'CNF',
            verification_method: 'chart_snapshot',
            label_confidence: 'verified',
          },
        },
      ],
    },
  ],
  withdrawal_log: [],
};

const mockRehearsalReport: RehearsalReportData = {
  schema_version: '1.0.0',
  run_id: 'REH_20260501T120000Z',
  run_timestamp: '2026-05-01T12:00:00Z',
  workspace: '/tmp/rehearsal',
  is_synthetic: true,
  overall_status: 'pass',
  software_rehearsal_passed: true,
  real_world_pilot_authorized: false,
  readiness_statement: 'SOFTWARE REHEARSAL PASSED - All 15 gates passed. REAL-WORLD PILOT AUTHORIZED: NO.',
  missing_gate_ids: [],
  gate_count: 15,
  failed_gate_count: 0,
  gates: [
    {
      gate_id: 'synthetic_batch_generation',
      title: 'Generate a labelled synthetic batch',
      evidence: ['Wrote 8 synthetic submissions.'],
      failures: [],
      warnings: [],
      human_actions: [],
    },
    {
      gate_id: 'pii_and_identifier_scan',
      title: 'PII scan',
      evidence: ['PII scan verified clean.'],
      failures: [],
      warnings: [],
      human_actions: [],
    },
  ],
};

describe('Operator UI Components', () => {
  it('OperatorBanner renders simulation warning and pilot non-authorization notice', () => {
    render(<OperatorBanner />);
    expect(screen.getByText(/Local Operator Workbench/i)).toBeInTheDocument();
    expect(screen.getByText(/authorize a real-world pilot/i)).toBeInTheDocument();
  });

  it('OperatorOverview displays summary counts and buttons', () => {
    const onSeed = vi.fn();
    const onRun = vi.fn();
    const onSelect = vi.fn();
    const onRefresh = vi.fn();

    render(
      <OperatorOverview
        status={mockStatus}
        batches={[mockBatchSummary]}
        selectedBatchId="BATCH_TEST_001"
        onSelectBatch={onSelect}
        onSeedBatch={onSeed}
        onRunRehearsal={onRun}
        onRefresh={onRefresh}
        isSeeding={false}
        isRehearsing={false}
      />,
    );

    expect(screen.getByText('BATCH_TEST_001 (8 submissions)')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Seed Synthetic Batch/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Run Synthetic Rehearsal/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Seed Synthetic Batch/i }));
    expect(onSeed).toHaveBeenCalled();
  });

  it('BatchAuditView renders PII scan and governance threshold indicators', () => {
    render(<BatchAuditView inspection={mockInspection} />);
    expect(screen.getByText(/Automated PII \/ Identifier Scan/i)).toBeInTheDocument();
    expect(screen.getByText(/CLEAN \(0 findings\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Governance & Scientific Thresholds/i)).toBeInTheDocument();
    expect(screen.getByText('2 trains')).toBeInTheDocument();
  });

  it('SubmissionReviewView renders submission table and submits review', async () => {
    const onReview = vi.fn().mockResolvedValue(undefined);
    render(<SubmissionReviewView inspection={mockInspection} onReview={onReview} />);

    expect(screen.getByText('SUB_001')).toBeInTheDocument();
    expect(screen.getByText('anon_grp_001')).toBeInTheDocument();

    // Click Review button
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Review SUB_001/i }));
    });

    // Review form appears
    expect(screen.getByText(/Review Submission: SUB_001/i)).toBeInTheDocument();
    const rationaleInput = screen.getByLabelText(/Review Rationale/i);
    await act(async () => {
      fireEvent.change(rationaleInput, { target: { value: 'Approved synthetic test' } });
    });

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /Save Review Decision/i }));
    });
    expect(onReview).toHaveBeenCalledWith('SUB_001', 'approved', 'operator_lead', 'Approved synthetic test');
  });

  it('WithdrawalLineageView submits withdrawal and renders export controls', async () => {
    const onWithdraw = vi.fn().mockResolvedValue(undefined);
    const onExport = vi.fn().mockResolvedValue(undefined);
    const onReconcile = vi.fn().mockResolvedValue(undefined);
    const onRefreshLineage = vi.fn().mockResolvedValue(undefined);

    render(
      <WithdrawalLineageView
        inspection={mockInspection}
        lineage={{
          batch_id: 'BATCH_TEST_001',
          export_path: '/export.json',
          is_synced: true,
          status: 'verified_in_sync',
          source_sha256_matches: true,
          recorded_source_sha256: 'abc',
          current_source_sha256: 'abc',
          withdrawn_groups_present: [],
          unapproved_groups_present: [],
          new_approved_groups_missing: [],
          violations: [],
        }}
        exportPreview={{
          batch_id: 'BATCH_TEST_001',
          total_considered: 8,
          approved_count: 2,
          excluded_count: 6,
          booking_groups_count: 2,
          passenger_reservations_count: 2,
          preview_booking_groups: [],
        }}
        onWithdraw={onWithdraw}
        onExport={onExport}
        onReconcile={onReconcile}
        onRefreshLineage={onRefreshLineage}
        isExporting={false}
        isReconciling={false}
      />,
    );

    expect(screen.getByText(/Record Participant Consent Withdrawal/i)).toBeInTheDocument();
    expect(screen.getByText(/Approved Dataset Export/i)).toBeInTheDocument();
    expect(screen.getByText(/Verified In Sync/i)).toBeInTheDocument();

    // Submit withdrawal
    await act(async () => {
      fireEvent.change(screen.getByLabelText(/Submission ID/i), { target: { value: 'SUB_001' } });
      fireEvent.change(screen.getByLabelText(/Withdrawal Reason/i), { target: { value: 'User request' } });
      fireEvent.click(screen.getByRole('button', { name: /Record Withdrawal/i }));
    });

    expect(onWithdraw).toHaveBeenCalledWith('SUB_001', 'User request', 'operator_lead');
  });

  it('RehearsalView displays 15-gate checklist and pilot authorization split', () => {
    const onRun = vi.fn().mockResolvedValue(undefined);
    render(
      <RehearsalView
        report={mockRehearsalReport}
        summaryText="SYNTHETIC SUMMARY TEXT"
        onRunRehearsal={onRun}
        isRunning={false}
      />,
    );

    expect(screen.getByRole('heading', { name: /SOFTWARE REHEARSAL PASSED/i })).toBeInTheDocument();
    expect(screen.getAllByText(/REAL-WORLD PILOT AUTHORIZED: NO/i).length).toBeGreaterThan(0);
    expect(screen.getByText('Generate a labelled synthetic batch')).toBeInTheDocument();

    // Expand gate
    fireEvent.click(screen.getByText('Generate a labelled synthetic batch'));
    expect(screen.getByText('Wrote 8 synthetic submissions.')).toBeInTheDocument();
  });
});

