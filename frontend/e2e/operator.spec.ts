import { test, expect } from '@playwright/test';

test.describe('Operator Workbench End-to-End Lifecycle', () => {
  test('loads operator workbench and navigates via header link', async ({ page }) => {
    await page.goto('/');

    // Click Operator link in header
    await page.getByRole('link', { name: 'Operator' }).click();
    await expect(page).toHaveURL(/\/operator/);

    // Verify main headings and safety banner
    await expect(page.getByRole('heading', { level: 1, name: /Operator Workbench/i })).toBeVisible();
    await expect(page.getByText(/Local Mode Active/i)).toBeVisible();
    await expect(page.getByText(/Local Operator Workbench — Offline Governance Simulation/i)).toBeVisible();
    await expect(page.getByText(/does not authorize a real-world pilot/i)).toBeVisible();
  });

  test('seeds synthetic batch, inspects audit, reviews submission, and withdraws with reconciliation', async ({ page }) => {
    await page.goto('/operator');

    // 1. Seed a synthetic batch
    const seedBtn = page.getByRole('button', { name: /Seed Synthetic Batch/i });
    await expect(seedBtn).toBeVisible();
    await seedBtn.click();
    await expect(seedBtn).toBeEnabled();

    // Verify batch selection and submission count in metrics
    await expect(page.getByText(/Active Batch:/i)).toBeVisible();

    // 2. Switch to Batch Audit tab
    await page.getByRole('button', { name: /Batch Audit/i }).click();
    await expect(page.getByRole('heading', { name: /Batch Metadata & Provenance/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Automated PII \/ Identifier Scan/i })).toBeVisible();
    await expect(page.getByText(/CLEAN \(0 findings\)/i)).toBeVisible();

    // 3. Switch to Submissions & Review tab
    await page.getByRole('button', { name: /Submissions & Review/i }).click();
    await expect(page.getByRole('heading', { name: /Prospective Submissions/i })).toBeVisible();

    // Click Review on the first submission
    const firstReviewBtn = page.getByRole('button', { name: /Review SUB_REH_001/i });
    await expect(firstReviewBtn).toBeVisible();
    await firstReviewBtn.click();

    // Fill in rationale and save decision
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByLabel(/Review Rationale/i)).toBeVisible();
    await page.getByLabel(/Review Rationale/i).fill('Verified synthetic test submission for E2E.');
    await page.getByRole('button', { name: /Save Review Decision/i }).click();

    // Verify success banner appears
    await expect(page.getByText(/transitioned to APPROVED/i)).toBeVisible();

    // 4. Switch to Withdrawals & Lineage tab
    await page.getByRole('button', { name: /Withdrawals & Lineage/i }).click();
    await expect(page.getByRole('heading', { name: /Record Participant Consent Withdrawal/i })).toBeVisible();

    // Execute Export first
    const exportBtn = page.getByRole('button', { name: /Execute Export/i });
    await exportBtn.click();
    await expect(page.getByText(/Verified In Sync/i)).toBeVisible();

    // Now record a withdrawal on the approved submission
    const withdrawSelect = page.getByLabel(/Submission ID:/i);
    await withdrawSelect.selectOption({ index: 1 });
    await page.getByLabel(/Withdrawal Reason:/i).fill('E2E simulated user opt-out request.');
    await page.getByRole('button', { name: /Record Withdrawal/i }).click();

    // Verify withdrawal audit log has the new entry
    await expect(page.getByText(/E2E simulated user opt-out request/i)).toBeVisible();

    // Verify lineage is now marked STALE
    await expect(page.getByText(/STALE: Withdrawn Records Present/i)).toBeVisible();

    // Click Reconcile Now to purge the withdrawn record
    const reconcileBtn = page.getByRole('button', { name: /Reconcile Now/i });
    await expect(reconcileBtn).toBeVisible();
    await reconcileBtn.click();

    // Lineage should return to Verified In Sync
    await expect(page.getByText(/Verified In Sync/i)).toBeVisible();

    // 5. Switch to 15-Gate Rehearsal tab
    await page.getByRole('button', { name: /15-Gate Rehearsal/i }).click();
    await expect(page.getByRole('heading', { name: /Prospective Lifecycle Synthetic Rehearsal/i })).toBeVisible();

    // Execute the rehearsal
    const runRehearsalBtn = page.getByRole('button', { name: /Execute 15-Gate Rehearsal/i });
    await runRehearsalBtn.click();

    // Check passing status and non-authorization callout
    await expect(page.getByRole('heading', { name: /SOFTWARE REHEARSAL PASSED/i })).toBeVisible({ timeout: 25000 });
    await expect(page.getByText(/REAL-WORLD PILOT AUTHORIZED: NO/i).first()).toBeVisible();

    // Verify individual gates
    await expect(page.getByText(/Generate a labelled synthetic batch/i)).toBeVisible();
    await expect(page.getByText(/Safe reconciliation/i)).toBeVisible();
  });
});

