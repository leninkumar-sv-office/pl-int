import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import StandingInstructionTable from './StandingInstructionTable';

const mockInstructions = [
  {
    id: 'si1', beneficiary: 'SBI SIP Fund', amount: 10000, frequency: 'Monthly',
    purpose: 'SIP', mandate_type: 'NACH', start_date: '2024-01-01',
    expiry_date: '2026-12-31', status: 'Active', remarks: '',
  },
];

const defaultProps = {
  instructions: mockInstructions,
  loading: false,
  siDashboard: { active_count: 1 },
  onAddSI: vi.fn(),
  onEditSI: vi.fn(),
  onDeleteSI: vi.fn(),
};

describe('StandingInstructionTable', () => {
  it('renders section title', () => {
    render(<StandingInstructionTable {...defaultProps} />);
    expect(screen.getByText(/Standing Instructions/)).toBeTruthy();
  });

  it('renders instruction beneficiary', () => {
    render(<StandingInstructionTable {...defaultProps} />);
    expect(screen.getAllByText(/SBI SIP Fund/).length).toBeGreaterThan(0);
  });

  it('renders active count badge', () => {
    render(<StandingInstructionTable {...defaultProps} />);
    expect(screen.getByText('1 active')).toBeTruthy();
  });

  it('shows empty state when no instructions', () => {
    render(<StandingInstructionTable {...defaultProps} instructions={[]} />);
    expect(screen.getByText(/No standing instructions yet/)).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<StandingInstructionTable {...defaultProps} instructions={[]} loading={true} />);
    expect(screen.getByText(/Loading standing instructions/)).toBeTruthy();
  });
});
