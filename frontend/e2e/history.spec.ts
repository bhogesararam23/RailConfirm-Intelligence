import { test, expect } from '@playwright/test';

test.describe('RailConfirm Prediction History and Reopening User Journey', () => {
  test('persists report when opted-in, lists in history, filters, and supports deletion', async ({ page }) => {
    // 1. Submit a prediction with "keep report" checked
    await page.goto('/');

    await page.getByRole('button', { name: /Solo Waitlist/i }).click();

    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 20);
    const dateStr = futureDate.toISOString().split('T')[0];
    await page.locator('#journey_date').fill(dateStr);

    const keepCheckbox = page.locator('#keep-report');
    await keepCheckbox.check();
    await expect(keepCheckbox).toBeChecked();

    await page.getByRole('button', { name: /Request estimate/i }).click();

    // Verify report appears and shows kept status
    await expect(page.getByRole('heading', { name: /Prediction report/i })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/Kept on this machine/i)).toBeVisible();

    // Extract prediction ID from report
    const predictionIdElement = page.locator('code.break-all').first();
    const predictionId = (await predictionIdElement.textContent())?.trim() || '';
    expect(predictionId.length).toBeGreaterThan(10);

    // 2. Navigate to History page
    await page.goto('/history');
    await expect(page.getByRole('heading', { name: /Kept reports/i })).toBeVisible();

    // Verify report is listed
    const reportSnippet = predictionId.slice(0, 8);
    await expect(page.getByText(`Report ${reportSnippet}`)).toBeVisible({ timeout: 10000 });

    // 3. Test filter and search
    const filterInput = page.getByLabel('Filter reports');
    await filterInput.fill('NON_EXISTENT_QUERY_9999');
    await expect(page.getByText(/No kept reports match the current filter/i)).toBeVisible();

    await page.getByRole('button', { name: /Clear filters/i }).click();
    await expect(page.getByText(`Report ${reportSnippet}`)).toBeVisible();

    // 4. Open stored report page
    await page.getByText(`Report ${reportSnippet}`).click();
    await expect(page).toHaveURL(new RegExp(`/prediction/${predictionId}`));
    await expect(page.getByRole('heading', { name: /Prediction report/i })).toBeVisible();
    await expect(page.getByText(/← View all kept reports/i)).toBeVisible();

    // 5. Delete report from stored report view
    await page.getByRole('button', { name: /Delete this report/i }).click();
    await expect(page.getByText(/Delete this stored report\? Nothing else will be removed/i)).toBeVisible();

    await page.getByRole('button', { name: /Confirm delete/i }).click();
    await expect(page.getByRole('heading', { name: /Report deleted/i })).toBeVisible();
  });
});
