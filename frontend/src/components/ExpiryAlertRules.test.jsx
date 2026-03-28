import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ExpiryAlertRules from './ExpiryAlertRules';

vi.mock('../services/api', () => ({
  getExpiryRules: vi.fn().mockResolvedValue([]),
  saveExpiryRule: vi.fn().mockResolvedValue({ id: 'r1', rule_type: 'days_before_maturity', days: 30, enabled: true }),
  deleteExpiryRule: vi.fn().mockResolvedValue({}),
}));

describe('ExpiryAlertRules', () => {
  it('renders alert button for FD category', () => {
    render(<ExpiryAlertRules category="fd" />);
    expect(screen.getByTitle('Manage alert rules')).toBeTruthy();
  });

  it('renders alert button for insurance category', () => {
    render(<ExpiryAlertRules category="insurance" />);
    expect(screen.getByTitle('Manage alert rules')).toBeTruthy();
  });

  it('shows dropdown when clicked', async () => {
    render(<ExpiryAlertRules category="fd" />);
    fireEvent.click(screen.getByTitle('Manage alert rules'));
    await waitFor(() => {
      expect(screen.getByText('Alert Rules')).toBeTruthy();
    });
  });

  it('shows "No alert rules configured" when empty', async () => {
    render(<ExpiryAlertRules category="fd" />);
    fireEvent.click(screen.getByTitle('Manage alert rules'));
    await waitFor(() => {
      expect(screen.getByText('No alert rules configured.')).toBeTruthy();
    });
  });

  it('shows + Add Rule button', async () => {
    render(<ExpiryAlertRules category="fd" />);
    fireEvent.click(screen.getByTitle('Manage alert rules'));
    await waitFor(() => {
      expect(screen.getByText('+ Add Rule')).toBeTruthy();
    });
  });

  it('shows add form when + Add Rule is clicked', async () => {
    render(<ExpiryAlertRules category="fd" />);
    fireEvent.click(screen.getByTitle('Manage alert rules'));
    await waitFor(() => {
      expect(screen.getByText('+ Add Rule')).toBeTruthy();
    });
    fireEvent.click(screen.getByText('+ Add Rule'));
    expect(screen.getByText('Select rule type...')).toBeTruthy();
    expect(screen.getByText('Save')).toBeTruthy();
  });

  it('renders rule options for stocks category', async () => {
    render(<ExpiryAlertRules category="stocks" />);
    fireEvent.click(screen.getByTitle('Manage alert rules'));
    await waitFor(() => {
      expect(screen.getByText('+ Add Rule')).toBeTruthy();
    });
    fireEvent.click(screen.getByText('+ Add Rule'));
    expect(screen.getByText('Select rule type...')).toBeTruthy();
  });

  it('shows existing rules with count badge', async () => {
    const { getExpiryRules } = await import('../services/api');
    getExpiryRules.mockResolvedValueOnce([
      { id: 'r1', rule_type: 'days_before_maturity', days: 30, enabled: true },
      { id: 'r2', rule_type: 'on_maturity', enabled: true },
    ]);
    render(<ExpiryAlertRules category="fd" />);
    await waitFor(() => {
      expect(screen.getByText(/2 rules/)).toBeTruthy();
    });
  });
});
