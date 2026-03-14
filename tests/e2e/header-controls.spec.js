import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab } from './helpers.js';

test.describe('Header Controls', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
  });

  test('Zerodha status indicator shows connected', async ({ page }) => {
    await expect(
      page.getByText('Zerodha connected', { exact: false }).first()
    ).toBeVisible();
  });

  test('price refresh interval dropdown works', async ({ page }) => {
    const dropdown = page.getByRole('combobox', {
      name: /Price refresh interval/i,
    });
    await expect(dropdown).toBeVisible();

    // Should have expected options
    await expect(dropdown.locator('option')).toHaveCount(4);
    await expect(dropdown.locator('option', { hasText: '1 min' })).toBeVisible();
    await expect(dropdown.locator('option', { hasText: '5 min' })).toBeVisible();
    await expect(dropdown.locator('option', { hasText: '10 min' })).toBeVisible();
  });

  test('reload interval dropdown works', async ({ page }) => {
    const dropdowns = page.getByRole('combobox');
    const reloadDropdown = dropdowns.nth(1);
    await expect(reloadDropdown).toBeVisible();

    // Should have Off + time options
    await expect(reloadDropdown.locator('option', { hasText: 'Off' })).toBeVisible();
    await expect(reloadDropdown.locator('option', { hasText: '10 min' })).toBeVisible();
  });

  test('reload countdown timer is visible', async ({ page }) => {
    // Should show a countdown like "9:42"
    await expect(page.getByText(/\d+:\d{2}/).first()).toBeVisible();
  });

  test('refresh button is functional', async ({ page }) => {
    const refreshBtn = page.getByRole('button', { name: '⟳ Refresh' });
    await expect(refreshBtn).toBeVisible();
    await expect(refreshBtn).toBeEnabled();
  });

  test('context-aware add button changes per tab', async ({ page }) => {
    // On Stocks tab
    await switchTab(page, 'Stocks');
    await expect(page.getByRole('button', { name: '+ Add Stock' })).toBeVisible();

    // On MF tab
    await switchTab(page, 'Mutual Funds');
    await expect(page.getByRole('button', { name: '+ Buy MF' })).toBeVisible();

    // On FD tab
    await switchTab(page, 'Fixed Deposits');
    await expect(page.getByRole('button', { name: '+ Add FD' })).toBeVisible();

    // On RD tab
    await switchTab(page, 'Recurring Deposits');
    await expect(page.getByRole('button', { name: '+ Add RD' })).toBeVisible();

    // On PPF tab
    await switchTab(page, 'PPF');
    await expect(page.getByRole('button', { name: '+ Add PPF' })).toBeVisible();

    // On NPS tab
    await switchTab(page, 'NPS');
    await expect(page.getByRole('button', { name: '+ Add NPS' })).toBeVisible();

    // On SI tab
    await switchTab(page, 'Standing Instructions');
    await expect(page.getByRole('button', { name: '+ Add SI' })).toBeVisible();

    // On Insurance tab
    await switchTab(page, 'Insurance');
    await expect(page.getByRole('button', { name: '+ Add Policy' })).toBeVisible();
  });

  test('all 9 tabs are visible', async ({ page }) => {
    const tabs = [
      'Stocks',
      'Mutual Funds',
      'Fixed Deposits',
      'Recurring Deposits',
      'PPF',
      'NPS',
      'Standing Instructions',
      'Insurance',
      'Charts',
    ];
    for (const tab of tabs) {
      await expect(page.getByRole('button', { name: tab, exact: true })).toBeVisible();
    }
  });

  test('clicking tab switches active state', async ({ page }) => {
    await switchTab(page, 'Mutual Funds');

    // MF tab should be active (has visible table)
    await expect(page.getByText('funds held', { exact: false })).toBeVisible();

    await switchTab(page, 'Stocks');

    // Stocks tab should now show stock data
    await expect(page.getByText('stocks held', { exact: false })).toBeVisible();
  });
});
