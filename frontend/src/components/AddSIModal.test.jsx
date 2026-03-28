import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddSIModal from './AddSIModal';

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
};

describe('AddSIModal', () => {
  it('renders modal title for new SI', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Add Standing Instruction')).toBeTruthy();
  });

  it('renders modal title for edit SI', () => {
    render(<AddSIModal {...defaultProps} initialData={{ id: 'si1', bank: 'HDFC', beneficiary: 'SBI MF', amount: 5000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByText('Edit Standing Instruction')).toBeTruthy();
  });

  it('renders Bank field', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Bank *')).toBeTruthy();
  });

  it('renders Beneficiary field', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Beneficiary *')).toBeTruthy();
  });

  it('renders Amount field', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText(/Amount/)).toBeTruthy();
  });

  it('renders Frequency dropdown', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Frequency')).toBeTruthy();
    expect(screen.getByDisplayValue('Monthly')).toBeTruthy();
  });

  it('renders Purpose dropdown', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Purpose')).toBeTruthy();
    expect(screen.getByDisplayValue('SIP')).toBeTruthy();
  });

  it('renders Mandate Type dropdown', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Mandate Type')).toBeTruthy();
    expect(screen.getByDisplayValue('NACH')).toBeTruthy();
  });

  it('renders Start Date and Expiry Date fields', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Start Date *')).toBeTruthy();
    expect(screen.getByText('Expiry Date *')).toBeTruthy();
  });

  it('renders Alert Before field', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Alert Before (days)')).toBeTruthy();
  });

  it('renders Status dropdown with default Active', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Status')).toBeTruthy();
    expect(screen.getByDisplayValue('Active')).toBeTruthy();
  });

  it('renders submit button for add mode', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('+ Add SI')).toBeTruthy();
  });

  it('renders submit button for edit mode', () => {
    render(<AddSIModal {...defaultProps} initialData={{ id: 'si1', bank: 'HDFC', beneficiary: 'SBI MF', amount: 5000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByText('Update SI')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddSIModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<AddSIModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('pre-fills form from initialData', () => {
    render(<AddSIModal {...defaultProps} initialData={{ id: 'si1', bank: 'HDFC Bank', beneficiary: 'SBI MF', amount: 5000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByDisplayValue('HDFC Bank')).toBeTruthy();
    expect(screen.getByDisplayValue('SBI MF')).toBeTruthy();
  });
});
