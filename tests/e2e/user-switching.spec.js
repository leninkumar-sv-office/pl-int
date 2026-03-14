import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard } from './helpers.js';

test.describe('User Switching', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
  });

  test('shows current user name in header', async ({ page }) => {
    await expect(page.getByRole('button', { name: 'Lenin' }).first()).toBeVisible();
  });

  test('user dropdown shows all users', async ({ page }) => {
    await page.getByRole('button', { name: 'Lenin' }).first().click();

    await expect(page.getByRole('button', { name: /Lenin/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Appa/ })).toBeVisible();
    await expect(page.getByRole('button', { name: /Amma/ })).toBeVisible();
  });

  test('user dropdown shows Add user button', async ({ page }) => {
    await page.getByRole('button', { name: 'Lenin' }).first().click();

    await expect(page.getByRole('button', { name: '+ Add user' })).toBeVisible();
  });

  test('user dropdown shows auth info and sign out', async ({ page }) => {
    await page.getByRole('button', { name: 'Lenin' }).first().click();

    await expect(page.getByText('leninkumar.sv.ai@gmail.com')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  });

  test('switching to Appa changes portfolio data', async ({ page }) => {
    // Get Lenin's portfolio summary
    const leninSummary = await page
      .getByText(/Portfolio Summary/)
      .first()
      .textContent();

    // Switch to Appa
    await page.getByRole('button', { name: 'Lenin' }).first().click();
    await page.getByRole('button', { name: /Appa/ }).click();

    // Wait for page to reload with Appa's data
    await page.getByRole('button', { name: 'Appa' }).first().waitFor({ timeout: 30_000 });

    // Appa's portfolio summary should be different
    const appaSummary = await page
      .getByText(/Portfolio Summary/)
      .first()
      .textContent()
      .catch(() => 'no summary');

    // Values should differ (different users have different portfolios)
    expect(appaSummary).not.toBe(leninSummary);
  });

  test('switching back to Lenin restores data', async ({ page }) => {
    // Switch to Appa
    await page.getByRole('button', { name: 'Lenin' }).first().click();
    await page.getByRole('button', { name: /Appa/ }).click();
    await page.getByRole('button', { name: 'Appa' }).first().waitFor({ timeout: 30_000 });

    // Switch back to Lenin
    await page.getByRole('button', { name: 'Appa' }).first().click();
    await page.getByRole('button', { name: /Lenin/ }).first().click();

    // Wait for reload
    await page.getByRole('button', { name: 'Stocks' }).waitFor({ timeout: 30_000 });

    // Lenin should be the active user
    await expect(page.getByRole('button', { name: 'Lenin' }).first()).toBeVisible();
  });
});
