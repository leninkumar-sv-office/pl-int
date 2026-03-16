import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AddFDModal from './AddFDModal';

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
};

describe('AddFDModal', () => {
  it('renders modal title for new FD', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Add Fixed Deposit')).toBeTruthy();
  });

  it('renders modal title for edit FD', () => {
    render(<AddFDModal {...defaultProps} initialData={{ id: 'fd1', bank: 'SBI', principal: 100000, interest_rate: 7.5, tenure_months: 12, start_date: '2024-01-01' }} />);
    expect(screen.getByText('Edit Fixed Deposit')).toBeTruthy();
  });

  it('renders Bank / Institution field', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Bank / Institution *')).toBeTruthy();
  });

  it('renders Type selector', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Type *')).toBeTruthy();
    expect(screen.getByText('Fixed Deposit (FD)')).toBeTruthy();
  });

  it('renders Interest Payout dropdown', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Interest Payout *')).toBeTruthy();
    // Default is Quarterly
    expect(screen.getByDisplayValue('Quarterly')).toBeTruthy();
  });

  it('renders payout options', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Monthly')).toBeTruthy();
    expect(screen.getByText('Quarterly')).toBeTruthy();
    expect(screen.getByText('Half-Yearly')).toBeTruthy();
    expect(screen.getByText('Annually')).toBeTruthy();
  });

  it('renders Principal Amount field', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText(/Principal Amount/)).toBeTruthy();
  });

  it('renders submit button', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('+ Add FD')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders Status selector', () => {
    render(<AddFDModal {...defaultProps} />);
    expect(screen.getByText('Status')).toBeTruthy();
    expect(screen.getByDisplayValue('Active')).toBeTruthy();
  });
});
