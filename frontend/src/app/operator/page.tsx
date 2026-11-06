'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
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
import type {
  BatchInspection,
  BatchSummary,
  ExportPreview,
  LineageInspection,
  OperatorStatus,
  RehearsalReportData,
} from '@/lib/types';
import { OperatorBanner } from '@/components/operator/OperatorBanner';
import { OperatorOverview } from '@/components/operator/OperatorOverview';
import { BatchAuditView } from '@/components/operator/BatchAuditView';
import { SubmissionReviewView } from '@/components/operator/SubmissionReviewView';
import { WithdrawalLineageView } from '@/components/operator/WithdrawalLineageView';
import { RehearsalView } from '@/components/operator/RehearsalView';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

type TabKey = 'overview' | 'audit' | 'review' | 'lineage' | 'rehearsal';

export default function OperatorPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview');
  const [status, setStatus] = useState<OperatorStatus | null>(null);
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [inspection, setInspection] = useState<BatchInspection | null>(null);
  const [lineage, setLineage] = useState<LineageInspection | null>(null);
  const [exportPreview, setExportPreview] = useState<ExportPreview | null>(null);
  const [rehearsalReport, setRehearsalReport] = useState<RehearsalReportData | null>(null);
  const [rehearsalSummary, setRehearsalSummary] = useState<string | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isDisabled, setIsDisabled] = useState<boolean>(false);

  const [isSeeding, setIsSeeding] = useState<boolean>(false);
  const [isRehearsing, setIsRehearsing] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isReconciling, setIsReconciling] = useState<boolean>(false);

  const loadBatchDetails = useCallback(async (batchId: string) => {
    try {
      const insp = await inspectBatch(batchId);
      setInspection(insp);

      // Load preview and lineage in background
      try {
        const prev = await previewExport(batchId);
        setExportPreview(prev);
      } catch {
        setExportPreview(null);
      }

      try {
        const lin = await inspectLineage(batchId);
        setLineage(lin);
      } catch {
        setLineage(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to inspect batch.');
    }
  }, []);

  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setIsDisabled(false);
    try {
      const stat = await fetchOperatorStatus();
      setStatus(stat);
      if (!stat.operator_enabled) {
        setIsDisabled(true);
        setLoading(false);
        return;
      }

      const batchRes = await fetchBatches();
      setBatches(batchRes.batches);

      if (batchRes.batches.length > 0) {
        const targetId = batchRes.batches[0].batch_id;
        setSelectedBatchId(targetId);
        await loadBatchDetails(targetId);
      }

      const latestReh = await fetchLatestRehearsal();
      if (latestReh) {
        setRehearsalReport(latestReh);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to connect to operator service.';
      if (msg.includes('Operator mode is disabled') || msg.includes('OPERATOR_DISABLED')) {
        setIsDisabled(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [loadBatchDetails]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const handleSelectBatch = async (batchId: string) => {
    setSelectedBatchId(batchId);
    await loadBatchDetails(batchId);
  };

  const handleSeedBatch = async () => {
    setIsSeeding(true);
    setError(null);
    try {
      const seeded = await seedSyntheticBatch();
      const stat = await fetchOperatorStatus();
      setStatus(stat);
      const bList = await fetchBatches();
      setBatches(bList.batches);
      setSelectedBatchId(seeded.batch_id);
      await loadBatchDetails(seeded.batch_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Seeding synthetic batch failed.');
    } finally {
      setIsSeeding(false);
    }
  };

  const handleRunRehearsal = async () => {
    setIsRehearsing(true);
    setError(null);
    try {
      const result = await runRehearsal();
      setRehearsalReport(result.report);
      setRehearsalSummary(result.summary_text);
      setActiveTab('rehearsal');
      // Refresh status counts
      const stat = await fetchOperatorStatus();
      setStatus(stat);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Rehearsal failed to execute.');
    } finally {
      setIsRehearsing(false);
    }
  };

  const handleReview = async (
    submissionId: string,
    action: string,
    reviewer: string,
    rationale: string,
  ) => {
    if (!selectedBatchId) return;
    await reviewSubmission(selectedBatchId, submissionId, action, reviewer, rationale);
    await loadBatchDetails(selectedBatchId);
    const stat = await fetchOperatorStatus();
    setStatus(stat);
  };

  const handleWithdraw = async (submissionId: string, reason: string, operator: string) => {
    if (!selectedBatchId) return;
    await withdrawSubmission(selectedBatchId, submissionId, reason, operator);
    await loadBatchDetails(selectedBatchId);
    const stat = await fetchOperatorStatus();
    setStatus(stat);
  };

  const handleExport = async () => {
    if (!selectedBatchId) return;
    setIsExporting(true);
    try {
      await executeExport(selectedBatchId);
      await loadBatchDetails(selectedBatchId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setIsExporting(false);
    }
  };

  const handleReconcile = async () => {
    if (!selectedBatchId) return;
    setIsReconciling(true);
    try {
      await reconcileExport(selectedBatchId);
      await loadBatchDetails(selectedBatchId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Reconciliation failed.');
    } finally {
      setIsReconciling(false);
    }
  };

  const handleRefreshLineage = async () => {
    if (!selectedBatchId) return;
    try {
      const lin = await inspectLineage(selectedBatchId);
      setLineage(lin);
    } catch {
      setLineage(null);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-gray-500">
        <LoadingSpinner size="lg" label="Loading operator workbench…" />
        <p className="mt-4 text-sm font-medium">Opening local operator workbench…</p>
      </div>
    );
  }

  if (isDisabled) {
    return (
      <div className="mx-auto max-w-3xl space-y-6 py-6">
        <OperatorBanner />
        <div className="rounded-lg border-2 border-dashed border-gray-300 bg-white p-8 text-center shadow-sm">
          <span className="text-3xl" aria-hidden="true">
            🔒
          </span>
          <h2 className="mt-2 text-xl font-bold text-gray-900">Operator Workbench is Disabled</h2>
          <p className="mt-2 text-sm text-gray-600 max-w-md mx-auto">
            By default, administrative and prospective data operator endpoints are disabled to ensure
            strict local-first isolation and prevent accidental exposure.
          </p>
          <div className="mt-6 rounded-md bg-gray-50 p-4 text-left border border-gray-200">
            <p className="text-xs font-semibold uppercase tracking-wider text-gray-600">
              How to enable locally:
            </p>
            <pre className="mt-2 font-mono text-xs text-gray-800 bg-white p-3 rounded border border-gray-200">
              # Start backend with operator enabled (loopback only){'\n'}
              RAILCONFIRM_OPERATOR_ENABLED=true uvicorn railconfirm.api.app:app
            </pre>
          </div>
          <div className="mt-6">
            <button
              type="button"
              onClick={loadInitialData}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 focus:outline-none"
            >
              Re-check Status
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-gray-200 pb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Operator Workbench</h1>
          <p className="text-sm text-gray-500">
            Local-only prospective data governance, inspection, review, and rehearsal controls.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
            ● Local Mode Active
          </span>
        </div>
      </div>

      <OperatorBanner />

      {error && (
        <div role="alert" className="rounded-md border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800">
          <p className="font-bold">Error:</p>
          <p>{error}</p>
        </div>
      )}

      {status && (
        <OperatorOverview
          status={status}
          batches={batches}
          selectedBatchId={selectedBatchId}
          onSelectBatch={handleSelectBatch}
          onSeedBatch={handleSeedBatch}
          onRunRehearsal={handleRunRehearsal}
          onRefresh={loadInitialData}
          isSeeding={isSeeding}
          isRehearsing={isRehearsing}
        />
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav aria-label="Operator sections" className="-mb-px flex space-x-6 text-sm font-medium">
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === 'overview'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            }`}
          >
            Overview
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('audit')}
            disabled={!inspection}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === 'audit'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } disabled:opacity-50`}
          >
            Batch Audit
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('review')}
            disabled={!inspection}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === 'review'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } disabled:opacity-50`}
          >
            Submissions & Review {inspection ? `(${inspection.submissions.length})` : ''}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('lineage')}
            disabled={!inspection}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === 'lineage'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            } disabled:opacity-50`}
          >
            Withdrawals & Lineage
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('rehearsal')}
            className={`border-b-2 py-3 px-1 text-sm font-medium ${
              activeTab === 'rehearsal'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700'
            }`}
          >
            15-Gate Rehearsal
          </button>
        </nav>
      </div>

      {/* Tab Panels */}
      {activeTab === 'overview' && inspection && (
        <BatchAuditView inspection={inspection} />
      )}

      {activeTab === 'audit' && inspection && (
        <BatchAuditView inspection={inspection} />
      )}

      {activeTab === 'review' && inspection && (
        <SubmissionReviewView inspection={inspection} onReview={handleReview} />
      )}

      {activeTab === 'lineage' && inspection && (
        <WithdrawalLineageView
          inspection={inspection}
          lineage={lineage}
          exportPreview={exportPreview}
          onWithdraw={handleWithdraw}
          onExport={handleExport}
          onReconcile={handleReconcile}
          onRefreshLineage={handleRefreshLineage}
          isExporting={isExporting}
          isReconciling={isReconciling}
        />
      )}

      {activeTab === 'rehearsal' && (
        <RehearsalView
          report={rehearsalReport}
          summaryText={rehearsalSummary}
          onRunRehearsal={handleRunRehearsal}
          isRunning={isRehearsing}
        />
      )}
    </div>
  );
}

