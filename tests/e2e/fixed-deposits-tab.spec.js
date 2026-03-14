import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab, apiGet } from './helpers.js';

test.describe('Fixed Deposits Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Fixed Deposits');
  });

  test('shows correct FD count matching API', async ({ page }) => {
    const apiData = await apiGet('/api/fixed-deposits/summary');
    const activeCount = apiData.filter((fd) => fd.status === 'active').length;
    const totalCount = apiData.length;

    await expect(page.getByText(`${activeCount} active`)).toBeVisible();
    await expect(page.getByText(`${totalCount} total`)).toBeVisible();
  });

  test('displays FD table with required columns', async ({ page }) => {
    const requiredColumns = [
      'Name',
      'Type',
      'Principal',
      'Rate',
      'Payout',
      'Tenure',
      'Start',
      'Maturity',
      'Status',
    ];
    for (const col of requiredColumns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('FD rows show correct data', async ({ page }) => {
    const apiData = await apiGet('/api/fixed-deposits/summary');
    if (apiData.length === 0) {
      await expect(page.getByText('No fixed deposits yet')).toBeVisible();
      return;
    }

    // Verify first FD name appears
    const firstName = apiData[0].name;
    await expect(page.getByText(firstName, { exact: false }).first()).toBeVisible();
  });

  test('has Add FD button', async ({ page }) => {
    await expect(page.getByRole('button', { name: '+ Add FD' })).toBeVisible();
  });

  test('has search box', async ({ page }) => {
    await expect(page.getByPlaceholder(/Search/i)).toBeVisible();
  });

  test('shows paid installments count', async ({ page }) => {
    const apiData = await apiGet('/api/fixed-deposits/summary');
    if (apiData.length === 0) return;

    // Should show "X/Y" format for paid installments
    await expect(page.getByText(/\d+\/\d+/).first()).toBeVisible();
  });
});
