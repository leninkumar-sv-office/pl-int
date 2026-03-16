import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import FixedDepositTable from './FixedDepositTable';

const mockDeposits = [
  {
    id: 'fd1', bank: 'SBI', name: 'SBI FD', principal: 100000, total_invested: 100000,
    interest_rate: 7.5, tenure_months: 12, type: 'FD',
    interest_payout: 'Quarterly', start_date: '2024-01-01',
    maturity_date: '2025-01-01', status: 'Active',
    interest_earned: 7500, maturity_amount: 107500,
  },
  {
    id: 'fd2', bank: 'HDFC Bank', name: 'HDFC MIS', principal: 200000, total_invested: 200000,
    interest_rate: 6.8, tenure_months: 24, type: 'MIS',
    interest_payout: 'Monthly', start_date: '2023-06-01',
    maturity_date: '2025-06-01', status: 'Active',
    interest_earned: 9000, maturity_amount: 209000,
  },
];

const defaultProps = {
  deposits: mockDeposits,
  loading: false,
  fdDashboard: { total_invested: 300000, active_count: 2, total_interest: 16500 },
  onAddFD: vi.fn(),
  onEditFD: vi.fn(),
  onDeleteFD: vi.fn(),
};

describe('FixedDepositTable', () => {
  it('renders section title', () => {
    render(<FixedDepositTable {...defaultProps} />);
    expect(screen.getByText(/Fixed Deposits/)).toBeTruthy();
  });

  it('renders FD bank name', () => {
    render(<FixedDepositTable {...defaultProps} />);
    expect(screen.getAllByText(/SBI FD/).length).toBeGreaterThan(0);
  });

  it('renders deposit count badge', () => {
    render(<FixedDepositTable {...defaultProps} />);
    expect(screen.getByText('2 active')).toBeTruthy();
  });

  it('shows empty state message when no deposits and no search', () => {
    render(<FixedDepositTable {...defaultProps} deposits={[]} />);
    expect(screen.getByText(/No fixed deposits yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<FixedDepositTable {...defaultProps} deposits={[]} loading={true} />);
    expect(screen.getByText(/Loading fixed deposits/)).toBeTruthy();
  });
});
