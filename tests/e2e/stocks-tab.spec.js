import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab, apiGet } from './helpers.js';

test.describe('Stocks Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Stocks');
  });

  test('shows correct number of held stocks matching API', async ({ page }) => {
    const apiData = await apiGet('/api/portfolio/stock-summary');
    const heldCount = apiData.filter((s) => s.total_held_qty > 0).length;

    await expect(page.getByText(`${heldCount} stocks held`)).toBeVisible();
  });

  test('shows profit/loss counts matching API', async ({ page }) => {
    const apiData = await apiGet('/api/portfolio/stock-summary');
    const held = apiData.filter((s) => s.total_held_qty > 0);
    const inProfit = held.filter((s) => s.unrealized_pl > 0).length;
    const inLoss = held.filter((s) => s.unrealized_pl <= 0).length;

    await expect(page.getByText(`${inProfit} in profit`)).toBeVisible();
    await expect(page.getByText(`${inLoss} in loss`)).toBeVisible();
  });

  test('displays stock table with required columns', async ({ page }) => {
    const requiredColumns = ['Stock', 'Held', 'Buy Price', 'Current Price', '52W Low', '52W High'];
    for (const col of requiredColumns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('displays stock rows with data', async ({ page }) => {
    const rows = page.locator('table tbody tr');
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);
  });

  test('expandable row shows lot details on click', async ({ page }) => {
    // Click the first stock row
    const firstRow = page.locator('table tbody tr').first();
    await firstRow.click();

    // Expanded content should show lot details
    await expect(page.getByText('Held Lots').first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('52-Week Range').first()).toBeVisible();
  });

  test('expanded row shows chart with timeframe tabs', async ({ page }) => {
    const firstRow = page.locator('table tbody tr').first();
    await firstRow.click();

    // Chart timeframe tabs
    await expect(page.getByRole('button', { name: '1Y' }).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: 'MAX' }).first()).toBeVisible();

    // SVG chart should render
    await expect(page.locator('td[colspan] svg').first()).toBeVisible();
  });

  test('expanded row has Buy and Sell buttons', async ({ page }) => {
    const firstRow = page.locator('table tbody tr').first();
    await firstRow.click();

    await expect(
      page.getByRole('button', { name: /Buy/i }).first()
    ).toBeVisible({ timeout: 5000 });
    await expect(page.getByRole('button', { name: 'Sell' }).first()).toBeVisible();
  });

  test('expanded row shows tax breakdown (LTCG/STCG)', async ({ page }) => {
    const firstRow = page.locator('table tbody tr').first();
    await firstRow.click();

    await expect(page.getByText('LTCG', { exact: false }).first()).toBeVisible({ timeout: 5000 });
    await expect(page.getByText('STCG', { exact: false }).first()).toBeVisible();
  });

  test('portfolio summary header shows total value and P&L', async ({ page }) => {
    await expect(
      page.getByText('Portfolio Summary', { exact: false }).first()
    ).toBeVisible();

    // Should contain rupee values
    await expect(page.getByText(/₹[\d,]+/).first()).toBeVisible();
  });
});
