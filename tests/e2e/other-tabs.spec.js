import { test, expect } from '@playwright/test';
import { authenticate, waitForDashboard, switchTab } from './helpers.js';

test.describe('PPF Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'PPF');
  });

  test('renders PPF tab with header and table', async ({ page }) => {
    await expect(page.getByText('Public Provident Fund')).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add PPF' })).toBeVisible();
  });

  test('has correct columns', async ({ page }) => {
    const columns = ['Account', 'Bank', 'Rate', 'Tenure', 'Start', 'Status'];
    for (const col of columns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('shows empty state or data', async ({ page }) => {
    const hasEmpty = (await page.getByText('No PPF accounts yet').count()) > 0;
    const hasRows = (await page.locator('table tbody tr').count()) > 0;
    expect(hasEmpty || hasRows).toBeTruthy();
  });
});

test.describe('NPS Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'NPS');
  });

  test('renders NPS tab with header and table', async ({ page }) => {
    await expect(page.getByText('National Pension System')).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add NPS' })).toBeVisible();
  });

  test('has correct columns', async ({ page }) => {
    const columns = ['Account', 'PRAN', 'Tier', 'Fund Manager', 'Status'];
    for (const col of columns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('shows empty state or data', async ({ page }) => {
    const hasEmpty = (await page.getByText('No NPS accounts yet').count()) > 0;
    const hasRows = (await page.locator('table tbody tr').count()) > 0;
    expect(hasEmpty || hasRows).toBeTruthy();
  });
});

test.describe('Standing Instructions Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Standing Instructions');
  });

  test('renders SI tab with header and table', async ({ page }) => {
    await expect(page.getByText('Standing Instructions').first()).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add SI' })).toBeVisible();
  });

  test('has correct columns', async ({ page }) => {
    const columns = ['Bank', 'Beneficiary', 'Amount', 'Frequency', 'Status'];
    for (const col of columns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('shows empty state or data', async ({ page }) => {
    const hasEmpty = (await page.getByText('No standing instructions yet').count()) > 0;
    const hasRows = (await page.locator('table tbody tr').count()) > 0;
    expect(hasEmpty || hasRows).toBeTruthy();
  });
});

test.describe('Insurance Tab', () => {
  test.beforeEach(async ({ page }) => {
    await authenticate(page);
    await waitForDashboard(page);
    await switchTab(page, 'Insurance');
  });

  test('renders Insurance tab with header and table', async ({ page }) => {
    await expect(page.getByText('Insurance Policies')).toBeVisible();
    await expect(page.getByRole('button', { name: '+ Add Policy' })).toBeVisible();
  });

  test('has correct columns', async ({ page }) => {
    const columns = ['Policy Name', 'Provider', 'Type', 'Premium', 'Status'];
    for (const col of columns) {
      await expect(
        page.getByRole('columnheader', { name: col, exact: false }).first()
      ).toBeVisible();
    }
  });

  test('shows empty state or data', async ({ page }) => {
    const hasEmpty = (await page.getByText('No insurance policies yet').count()) > 0;
    const hasRows = (await page.locator('table tbody tr').count()) > 0;
    expect(hasEmpty || hasRows).toBeTruthy();
  });
});
