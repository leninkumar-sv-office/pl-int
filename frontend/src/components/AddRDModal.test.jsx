import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddRDModal from './AddRDModal';

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
};

describe('AddRDModal', () => {
  it('renders modal title for new RD', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Add Recurring Deposit')).toBeTruthy();
  });

  it('renders modal title for edit RD', () => {
    render(<AddRDModal {...defaultProps} mode="edit" initialData={{ id: 'rd1', bank: 'SBI', monthly_amount: 5000, interest_rate: 7.5, tenure_months: 12, start_date: '2024-01-01' }} />);
    expect(screen.getByText('Edit Recurring Deposit')).toBeTruthy();
  });

  it('renders installment mode', () => {
    render(<AddRDModal {...defaultProps} mode="installment" initialData={{ id: 'rd1', bank: 'SBI', monthly_amount: 5000 }} />);
    expect(screen.getByText('Add Installment')).toBeTruthy();
  });

  it('renders Bank field', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Bank / Institution *')).toBeTruthy();
  });

  it('renders Monthly Amount field', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText(/Monthly Amount/)).toBeTruthy();
  });

  it('renders Interest Rate field', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Interest Rate (%) *')).toBeTruthy();
  });

  it('renders Tenure field', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Tenure (months) *')).toBeTruthy();
  });

  it('renders Compounding Frequency dropdown', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Compounding Frequency *')).toBeTruthy();
  });

  it('renders Start Date field', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Start Date *')).toBeTruthy();
  });

  it('renders Status dropdown with default Active', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Status')).toBeTruthy();
    expect(screen.getByDisplayValue('Active')).toBeTruthy();
  });

  it('renders submit button for add mode', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('+ Add RD')).toBeTruthy();
  });

  it('renders submit button for edit mode', () => {
    render(<AddRDModal {...defaultProps} mode="edit" initialData={{ id: 'rd1', bank: 'SBI', monthly_amount: 5000, interest_rate: 7.5, tenure_months: 12, start_date: '2024-01-01' }} />);
    expect(screen.getByText('Update RD')).toBeTruthy();
  });

  it('renders installment submit button', () => {
    render(<AddRDModal {...defaultProps} mode="installment" initialData={{ id: 'rd1', bank: 'SBI', monthly_amount: 5000 }} />);
    expect(screen.getByText('+ Add Installment')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddRDModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<AddRDModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows installment fields in installment mode', () => {
    render(<AddRDModal {...defaultProps} mode="installment" initialData={{ id: 'rd1', bank: 'SBI', monthly_amount: 5000 }} />);
    expect(screen.getByText('Date *')).toBeTruthy();
    expect(screen.getByText(/Amount/)).toBeTruthy();
  });
});
