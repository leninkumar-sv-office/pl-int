import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab } from './helpers.js';

test.describe('Charts Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Charts');
  });

  test('renders charts with SVG elements', async ({ page }) => {
    // Charts tab should have SVG-based charts (recharts)
    const svgs = page.locator('svg');
    const count = await svgs.count();
    expect(count).toBeGreaterThan(0);
  });

  test('shows Unrealized P&L chart', async ({ page }) => {
    await expect(page.getByText('Unrealized P&L', { exact: false }).first()).toBeVisible();
  });

  test('shows Portfolio Composition chart', async ({ page }) => {
    await expect(page.getByText('Portfolio Composition', { exact: false }).first()).toBeVisible();
  });

  test('charts contain stock symbols', async ({ page }) => {
    // Charts should reference actual stock symbols
    const pageText = await page.innerText('body');
    // At least some stock symbols should appear in chart labels
    const hasStockSymbols =
      pageText.includes('ITC') || pageText.includes('LT') || pageText.includes('RALLIS');
    expect(hasStockSymbols).toBeTruthy();
  });
});
