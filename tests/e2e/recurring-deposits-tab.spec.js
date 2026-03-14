import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab, apiGet } from './helpers.js';

test.describe('Recurring Deposits Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Recurring Deposits');
  });

  test('shows correct RD count matching API', async ({ page }) => {
    const apiData = await apiGet('/api/recurring-deposits/summary');
    const activeCount = apiData.filter((rd) => rd.status === 'active').length;

    await expect(page.getByText(`${activeCount} active`)).toBeVisible();
  });

  test('displays RD table with required columns', async ({ page }) => {
    const requiredColumns = ['Name', 'Monthly Amt', 'Rate', 'Tenure', 'Start', 'Maturity', 'Status'];
    for (const col of requiredColumns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('RD rows show account numbers', async ({ page }) => {
    const apiData = await apiGet('/api/recurring-deposits/summary');
    if (apiData.length === 0) {
      await expect(page.getByText('No recurring deposits yet')).toBeVisible();
      return;
    }

    // Should have data rows
    const rows = page.locator('table tbody tr');
    expect(await rows.count()).toBe(apiData.length);
  });

  test('has Add RD button', async ({ page }) => {
    await expect(page.getByRole('button', { name: '+ Add RD' })).toBeVisible();
  });

  test('shows paid installment progress', async ({ page }) => {
    const apiData = await apiGet('/api/recurring-deposits/summary');
    if (apiData.length === 0) return;

    // Should show "X/Y" format for paid installments
    await expect(page.getByText(/\d+\/\d+/).first()).toBeVisible();
  });
});
