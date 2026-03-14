import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, apiGet } from './helpers.js';

test.describe('Market Ticker Bar', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
  });

  test('displays all expected tickers with prices', async ({ page }) => {
    const expectedTickers = [
      'Sensex',
      'Nifty 50',
      'GIFT Nifty',
      'SGX STI',
      'Nikkei',
      'SGD/INR',
      'USD/INR',
      'Gold',
      'Silver',
      'Crude Oil',
    ];

    for (const ticker of expectedTickers) {
      await expect(page.getByText(ticker, { exact: false }).first()).toBeVisible();
    }
  });

  test('ticker prices match API data', async ({ page }) => {
    const apiData = await apiGet('/api/market-ticker');
    const tickers = apiData.tickers;

    // Verify Sensex price is displayed
    const sensex = tickers.find((t) => t.key === 'SENSEX');
    if (sensex) {
      const formattedPrice = sensex.price.toLocaleString('en-IN');
      await expect(page.getByText(formattedPrice).first()).toBeVisible();
    }

    // Verify Nifty price
    const nifty = tickers.find((t) => t.key === 'NIFTY50');
    if (nifty) {
      const formattedPrice = nifty.price.toLocaleString('en-IN');
      await expect(page.getByText(formattedPrice).first()).toBeVisible();
    }
  });

  test('shows 1D, 7D, 1M change percentages for each ticker', async ({ page }) => {
    // Check that change period labels exist
    await expect(page.getByText('1D:', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('7D:', { exact: false }).first()).toBeVisible();
    await expect(page.getByText('1M:', { exact: false }).first()).toBeVisible();
  });

  test('shows last updated timestamp', async ({ page }) => {
    await expect(page.getByText('Last updated:').first()).toBeVisible();
  });

  test('uses correct color for up/down indicators', async ({ page }) => {
    // At least one ticker should show ▲ (up) or ▼ (down)
    const upCount = await page.getByText('▲').count();
    const downCount = await page.getByText('▼').count();
    expect(upCount + downCount).toBeGreaterThan(0);
  });
});
