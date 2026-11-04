import { test, expect } from '@playwright/test';

test.describe('RailConfirm Journey and Prediction User Journey', () => {
  test('loads home page with initial form and journey controls', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/RailConfirm/i);
    await expect(page.getByRole('heading', { name: /Journey details/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Passenger statuses/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Request estimate/i })).toBeVisible();
  });

  test('validates required fields before submitting to backend', async ({ page }) => {
    await page.goto('/');

    // Clear train number
    const trainInput = page.locator('#train_number');
    await trainInput.fill('');

    // Submit form
    await page.getByRole('button', { name: /Request estimate/i }).click();

    // Verify client-side error alert appears
    const alert = page.locator('div[role="alert"]').filter({ hasText: 'Fix these before sending' });
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/Train number is required/i);
  });

  test('applies preset scenarios and auto-populates journey and passenger rows', async ({ page }) => {
    await page.goto('/');

    // Click "Family Mixed WL & RAC" preset
    await page.getByRole('button', { name: /Family Mixed WL & RAC/i }).click();

    // Verify announcement
    await expect(page.getByText(/Loaded preset scenario: Family Mixed WL & RAC/i)).toBeVisible();

    // Verify fields populated
    await expect(page.locator('#train_number')).toHaveValue('12952');
    await expect(page.locator('#boarding_station')).toHaveValue('MMCT');
    await expect(page.locator('#destination_station')).toHaveValue('NDLS');

    // Verify passenger count is 3
    await expect(page.getByRole('heading', { name: /Passenger statuses \(3\)/i })).toBeVisible();
  });

  test('duplicates passenger row with auto-incremented status number', async ({ page }) => {
    await page.goto('/');

    // Load Family preset (3 passengers: RAC 5 -> CNF, RAC 6 -> RAC 1, GNWL/8 -> RAC 2)
    await page.getByRole('button', { name: /Family Mixed WL & RAC/i }).click();
    await expect(page.getByRole('heading', { name: /Passenger statuses \(3\)/i })).toBeVisible();

    // Click duplicate on Passenger 3 (GNWL/8 -> RAC 2)
    await page.getByRole('button', { name: 'Duplicate passenger 3' }).click();

    // Verify passenger count is now 4
    await expect(page.getByRole('heading', { name: /Passenger statuses \(4\)/i })).toBeVisible();

    // Verify passenger 4 row has incremented status (GNWL/9 and RAC 3)
    const passenger4Original = page.locator('input[id$="-original"]').nth(3);
    const passenger4Current = page.locator('input[id$="-current"]').nth(3);
    await expect(passenger4Original).toHaveValue('GNWL/9');
    await expect(passenger4Current).toHaveValue('RAC 3');
  });

  test('submits valid journey and renders structured abstention report', async ({ page }) => {
    await page.goto('/');

    // Load Solo Waitlist preset
    await page.getByRole('button', { name: /Solo Waitlist/i }).click();

    // Ensure journey date is comfortably in the future (e.g. 15 days ahead)
    const futureDate = new Date();
    futureDate.setDate(futureDate.getDate() + 15);
    const dateStr = futureDate.toISOString().split('T')[0];
    await page.locator('#journey_date').fill(dateStr);

    // Set estimation as of today
    const now = new Date();
    const localNow = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
      .toISOString()
      .slice(0, 16);
    await page.locator('#prediction_at').fill(localNow);

    // Submit estimate
    await page.getByRole('button', { name: /Request estimate/i }).click();

    // Verify prediction report is displayed
    await expect(page.getByRole('heading', { name: /Prediction report/i })).toBeVisible({ timeout: 15000 });

    // Under ADR-0007 / no approved real dataset, model version must be no_model_v0
    await expect(page.locator('code').filter({ hasText: 'no_model_v0' })).toBeVisible();

    // Evidence context or limitations must be clearly stated
    await expect(page.getByText(/Evidence context and limitations/i)).toBeVisible();

    // Export JSON button should be available
    await expect(page.getByRole('button', { name: /Export JSON/i })).toBeVisible();

    // Reset back to form
    await page.getByRole('button', { name: /← New prediction/i }).click();
    await expect(page.getByRole('heading', { name: /Journey details/i })).toBeVisible();
  });
});
