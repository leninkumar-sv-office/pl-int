import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import PPFTable from './PPFTable';

const mockAccounts = [
  {
    id: 'ppf1', account_name: 'SBI PPF', account_number: 'PPF123',
    bank: 'SBI', opening_date: '2020-04-01',
    current_balance: 250000, net_invested: 220000,
    total_interest: 30000, status: 'Active',
    contributions: [],
  },
];

const defaultProps = {
  accounts: mockAccounts,
  loading: false,
  ppfDashboard: { net_invested: 220000, current_balance: 250000, active_count: 1 },
  onAddPPF: vi.fn(),
  onEditPPF: vi.fn(),
  onDeletePPF: vi.fn(),
  onAddContribution: vi.fn(),
  onWithdrawPPF: vi.fn(),
  onRedeemPPF: vi.fn(),
};

describe('PPFTable', () => {
  it('renders section title', () => {
    render(<PPFTable {...defaultProps} />);
    expect(screen.getByText(/Public Provident Fund/)).toBeTruthy();
  });

  it('renders PPF account name', () => {
    render(<PPFTable {...defaultProps} />);
    expect(screen.getAllByText(/SBI PPF/).length).toBeGreaterThan(0);
  });

  it('renders active count badge', () => {
    render(<PPFTable {...defaultProps} />);
    expect(screen.getByText('1 active')).toBeTruthy();
  });

  it('shows empty state when no accounts', () => {
    render(<PPFTable {...defaultProps} accounts={[]} />);
    expect(screen.getByText(/No PPF accounts yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<PPFTable {...defaultProps} accounts={[]} loading={true} />);
    expect(screen.getByText(/Loading PPF accounts/)).toBeTruthy();
  });
});
