import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import InsuranceTable from './InsuranceTable';

const mockPolicies = [
  {
    id: 'ins1', policy_name: 'Star Health Policy', provider: 'Star Health Insurance',
    type: 'Health', premium: 15000, coverage: 500000,
    start_date: '2024-04-01', expiry_date: '2025-03-31', status: 'Active',
    remarks: '',
  },
];

const defaultProps = {
  policies: mockPolicies,
  loading: false,
  insuranceDashboard: { active_count: 1, total_premium: 15000 },
  onAddInsurance: vi.fn(),
  onEditInsurance: vi.fn(),
  onDeleteInsurance: vi.fn(),
};

describe('InsuranceTable', () => {
  it('renders section title', () => {
    render(<InsuranceTable {...defaultProps} />);
    expect(screen.getByText(/Insurance Policies/)).toBeTruthy();
  });

  it('renders policy provider', () => {
    render(<InsuranceTable {...defaultProps} />);
    expect(screen.getAllByText(/Star Health Insurance/).length).toBeGreaterThan(0);
  });

  it('renders active count badge', () => {
    render(<InsuranceTable {...defaultProps} />);
    expect(screen.getByText('1 active')).toBeTruthy();
  });

  it('shows empty state when no policies', () => {
    render(<InsuranceTable {...defaultProps} policies={[]} />);
    expect(screen.getByText(/No insurance policies yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<InsuranceTable {...defaultProps} policies={[]} loading={true} />);
    expect(screen.getByText(/Loading insurance policies/)).toBeTruthy();
  });
});
