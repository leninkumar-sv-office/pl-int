import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import RecurringDepositTable from './RecurringDepositTable';

const mockRDs = [
  {
    id: 'rd1', bank: 'Post Office', name: 'Post Office RD',
    monthly_amount: 5000, interest_rate: 6.7, tenure_months: 12,
    compounding: 'Quarterly', start_date: '2024-01-01',
    maturity_date: '2025-01-01', status: 'Active',
    total_deposited: 60000, interest_accrued: 2200, maturity_amount: 62200,
    installments_paid: 3,
  },
];

const defaultProps = {
  deposits: mockRDs,
  loading: false,
  rdDashboard: { total_deposited: 60000, active_count: 1 },
  onAddRD: vi.fn(),
  onEditRD: vi.fn(),
  onDeleteRD: vi.fn(),
  onAddInstallment: vi.fn(),
};

describe('RecurringDepositTable', () => {
  it('renders section title', () => {
    render(<RecurringDepositTable {...defaultProps} />);
    expect(screen.getByText(/Recurring Deposits/)).toBeTruthy();
  });

  it('renders RD bank name', () => {
    render(<RecurringDepositTable {...defaultProps} />);
    expect(screen.getAllByText(/Post Office/).length).toBeGreaterThan(0);
  });

  it('renders active count badge', () => {
    render(<RecurringDepositTable {...defaultProps} />);
    expect(screen.getByText('1 active')).toBeTruthy();
  });

  it('shows empty state when no deposits', () => {
    render(<RecurringDepositTable {...defaultProps} deposits={[]} />);
    expect(screen.getByText(/No recurring deposits yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<RecurringDepositTable {...defaultProps} deposits={[]} loading={true} />);
    expect(screen.getByText(/Loading recurring deposits/)).toBeTruthy();
  });
});
