import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddPPFModal from './AddPPFModal';

const defaultProps = {
  onSubmit: vi.fn(),
  onClose: vi.fn(),
};

describe('AddPPFModal', () => {
  it('renders modal title for new account', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Add PPF Account')).toBeTruthy();
  });

  it('renders modal title for edit mode', () => {
    render(<AddPPFModal {...defaultProps} mode="edit" initialData={{ id: 'ppf1', account_name: 'PPF Self', bank: 'SBI', start_date: '2020-01-01' }} />);
    expect(screen.getByText('Edit PPF Account')).toBeTruthy();
  });

  it('renders modal title for contribution mode', () => {
    render(<AddPPFModal {...defaultProps} mode="contribution" initialData={{ id: 'ppf1', account_name: 'My PPF' }} />);
    expect(screen.getByText(/Add Contribution — My PPF/)).toBeTruthy();
  });

  it('renders Account Name field', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Account Name *')).toBeTruthy();
  });

  it('renders Bank / Institution field', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Bank / Institution *')).toBeTruthy();
  });

  it('renders Interest Rate field', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Interest Rate (%) *')).toBeTruthy();
  });

  it('renders Tenure field', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Tenure (years)')).toBeTruthy();
  });

  it('renders Start Date field', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Start Date *')).toBeTruthy();
  });

  it('renders Payment Type toggle', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Payment Type')).toBeTruthy();
    expect(screen.getByText('One-time')).toBeTruthy();
    expect(screen.getByText('SIP (Recurring)')).toBeTruthy();
  });

  it('renders submit button for add mode', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('+ Add PPF')).toBeTruthy();
  });

  it('renders submit button for edit mode', () => {
    render(<AddPPFModal {...defaultProps} mode="edit" initialData={{ id: 'ppf1', account_name: 'PPF Self', bank: 'SBI', start_date: '2020-01-01' }} />);
    expect(screen.getByText('Update PPF')).toBeTruthy();
  });

  it('renders submit button for contribution mode', () => {
    render(<AddPPFModal {...defaultProps} mode="contribution" initialData={{ id: 'ppf1', account_name: 'My PPF' }} />);
    expect(screen.getByText('+ Add Contribution')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<AddPPFModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows projection preview for new account', () => {
    render(<AddPPFModal {...defaultProps} />);
    expect(screen.getByText(/Projection assuming/)).toBeTruthy();
    expect(screen.getByText('Total Deposited')).toBeTruthy();
    expect(screen.getByText('Interest Earned')).toBeTruthy();
    expect(screen.getByText('Maturity Value')).toBeTruthy();
  });

  it('shows contribution fields in contribution mode', () => {
    render(<AddPPFModal {...defaultProps} mode="contribution" initialData={{ id: 'ppf1', account_name: 'My PPF' }} />);
    expect(screen.getByText('Date *')).toBeTruthy();
    expect(screen.getByText(/Amount/)).toBeTruthy();
  });

  it('shows SIP fields when SIP payment type selected', () => {
    render(<AddPPFModal {...defaultProps} />);
    fireEvent.click(screen.getByText('SIP (Recurring)'));
    expect(screen.getByText(/SIP Amount/)).toBeTruthy();
    expect(screen.getByText('Frequency')).toBeTruthy();
  });
});
