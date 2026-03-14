import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab, apiGet } from './helpers.js';

test.describe('Mutual Funds Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Mutual Funds');
  });

  test('shows correct held fund count matching API', async ({ page }) => {
    const apiData = await apiGet('/api/mutual-funds/summary');
    const heldCount = apiData.filter((f) => f.total_held_units > 0).length;

    expect(heldCount).toBeGreaterThan(0);
    await expect(page.getByText(`${heldCount} funds held`)).toBeVisible();
  });

  test('shows profit/loss counts', async ({ page }) => {
    await expect(page.getByText(/\d+ in profit/)).toBeVisible();
    await expect(page.getByText(/\d+ in loss/)).toBeVisible();
  });

  test('displays fund table with required columns', async ({ page }) => {
    const requiredColumns = [
      'Fund',
      'Units',
      'Avg NAV',
      'Current NAV',
      '52W Low',
      '52W High',
      'Current Value',
      'Invested',
      'Unrealized P&L',
    ];
    for (const col of requiredColumns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('groups funds by AMC', async ({ page }) => {
    const apiData = await apiGet('/api/mutual-funds/summary');
    const heldFunds = apiData.filter((f) => f.total_held_units > 0);

    // Extract unique AMC names (first word of fund name)
    const amcNames = [...new Set(heldFunds.map((f) => f.fund_name.split(' ')[0]))];

    // At least some AMC group headers should be visible
    let foundAmcs = 0;
    for (const amc of amcNames) {
      const count = await page.getByText(amc, { exact: false }).count();
      if (count > 0) foundAmcs++;
    }
    expect(foundAmcs).toBeGreaterThan(0);
  });

  test('held-only filter works', async ({ page }) => {
    const apiData = await apiGet('/api/mutual-funds/summary');
    const totalCount = apiData.length;
    const heldCount = apiData.filter((f) => f.total_held_units > 0).length;

    // With "Held only" checked, should show fewer funds
    await expect(page.getByText(`${heldCount} of ${totalCount} funds`)).toBeVisible();

    // Uncheck "Held only"
    await page.getByRole('checkbox', { name: 'Held only' }).click();

    // Now should show more funds or same total
    await expect(page.getByText(`${totalCount} of ${totalCount} funds`)).toBeVisible({
      timeout: 3000,
    });

    // Re-check "Held only"
    await page.getByRole('checkbox', { name: 'Held only' }).click();
    await expect(page.getByText(`${heldCount} of ${totalCount} funds`)).toBeVisible();
  });

  test('search filter works', async ({ page }) => {
    const searchBox = page.getByPlaceholder('Search funds by name or code');
    await searchBox.fill('SBI');

    // Should filter to only SBI funds
    await expect(page.getByText(/\d+ of \d+ funds/)).toBeVisible();

    // SBI text should be visible in results
    await expect(page.getByText('SBI', { exact: false }).first()).toBeVisible();

    // Clear search
    await page.getByText('✕').click();
  });

  test('expandable row shows lot details', async ({ page }) => {
    // Click first fund row (not AMC header)
    const fundRow = page.locator('table tbody tr[cursor=pointer], table tbody tr').nth(1);
    await fundRow.click();

    // Should show expanded content
    await expect(page.getByText('Held Lots').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('52-Week Range').first()).toBeVisible();
  });

  test('expanded row shows NAV history chart', async ({ page }) => {
    const fundRow = page.locator('table tbody tr').nth(1);
    await fundRow.click();

    // Chart timeframe buttons
    await expect(page.getByRole('button', { name: '1Y' }).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: 'MAX' }).first()).toBeVisible();
  });

  test('expanded row shows redemption history', async ({ page }) => {
    const fundRow = page.locator('table tbody tr').nth(1);
    await fundRow.click();

    // Check for redemptions section (if fund has any)
    const hasRedemptions = (await page.getByText('Redemptions').count()) > 0;
    const hasRedeemed = (await page.getByText('redeemed').count()) > 0;
    // Either redemptions section or "redeemed" count should exist
    expect(hasRedemptions || hasRedeemed).toBeTruthy();
  });

  test('expanded row shows tax summary', async ({ page }) => {
    const fundRow = page.locator('table tbody tr').nth(1);
    await fundRow.click();

    await expect(page.getByText('LTCG', { exact: false }).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('STCG', { exact: false }).first()).toBeVisible();
  });

  test('shows NAV with 1D/7D/1M changes', async ({ page }) => {
    // Each fund row should show NAV change periods
    await expect(page.getByText('1D:', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('7D:', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('1M:', { exact: false }).first()).toBeVisible();
  });

  test('Import CDSL CAS button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Import CDSL CAS' })).toBeVisible();
  });

  test('Buy MF button is visible', async ({ page }) => {
    await expect(page.getByRole('button', { name: '+ Buy MF' })).toBeVisible();
  });
});
