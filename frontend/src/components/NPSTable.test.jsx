import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import NPSTable from './NPSTable';

const mockAccounts = [
  {
    id: 'nps1', account_name: 'HDFC NPS', pran: 'PRAN123',
    fund_manager: 'HDFC', opening_date: '2021-04-01',
    current_value: 180000, total_contributed: 150000,
    total_gain: 30000, status: 'Active',
    contributions: [],
  },
];

const defaultProps = {
  accounts: mockAccounts,
  loading: false,
  npsDashboard: { total_contributed: 150000, current_value: 180000, active_count: 1 },
  onAddNPS: vi.fn(),
  onEditNPS: vi.fn(),
  onDeleteNPS: vi.fn(),
  onAddContribution: vi.fn(),
};

describe('NPSTable', () => {
  it('renders section title', () => {
    render(<NPSTable {...defaultProps} />);
    expect(screen.getByText(/National Pension System/)).toBeTruthy();
  });

  it('renders NPS account name', () => {
    render(<NPSTable {...defaultProps} />);
    expect(screen.getAllByText(/HDFC NPS/).length).toBeGreaterThan(0);
  });

  it('renders active count badge', () => {
    render(<NPSTable {...defaultProps} />);
    expect(screen.getByText('1 active')).toBeTruthy();
  });

  it('shows empty state when no accounts', () => {
    render(<NPSTable {...defaultProps} accounts={[]} />);
    expect(screen.getByText(/No NPS accounts yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<NPSTable {...defaultProps} accounts={[]} loading={true} />);
    expect(screen.getByText(/Loading NPS accounts/)).toBeTruthy();
  });
});
