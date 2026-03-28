import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddInsuranceModal from './AddInsuranceModal';

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
};

describe('AddInsuranceModal', () => {
  it('renders modal title for new policy', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Add Insurance Policy')).toBeTruthy();
  });

  it('renders modal title for edit policy', () => {
    render(<AddInsuranceModal {...defaultProps} initialData={{ id: 'ins1', policy_name: 'Star Health', provider: 'Star', premium: 15000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByText('Edit Insurance Policy')).toBeTruthy();
  });

  it('renders Policy Name field', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Policy Name *')).toBeTruthy();
  });

  it('renders Provider field', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Provider *')).toBeTruthy();
  });

  it('renders Type dropdown with default Health', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Type')).toBeTruthy();
    expect(screen.getByDisplayValue('Health')).toBeTruthy();
  });

  it('renders type options', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Health')).toBeTruthy();
    expect(screen.getByText('Life')).toBeTruthy();
    expect(screen.getByText('Car')).toBeTruthy();
    expect(screen.getByText('Bike')).toBeTruthy();
  });

  it('renders Payment Frequency dropdown', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Payment Frequency')).toBeTruthy();
    expect(screen.getByDisplayValue('Annual')).toBeTruthy();
  });

  it('renders Premium field', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText(/Premium/)).toBeTruthy();
  });

  it('renders Coverage field', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText(/Coverage/)).toBeTruthy();
  });

  it('renders Start Date and Expiry Date fields', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Start Date *')).toBeTruthy();
    expect(screen.getByText('Expiry Date *')).toBeTruthy();
  });

  it('renders Status selector with default Active', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Status')).toBeTruthy();
    expect(screen.getByDisplayValue('Active')).toBeTruthy();
  });

  it('renders submit button for new policy', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('+ Add Policy')).toBeTruthy();
  });

  it('renders submit button for edit policy', () => {
    render(<AddInsuranceModal {...defaultProps} initialData={{ id: 'ins1', policy_name: 'Test', provider: 'Test', premium: 1000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByText('Update Policy')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddInsuranceModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<AddInsuranceModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('pre-fills form from initialData', () => {
    render(<AddInsuranceModal {...defaultProps} initialData={{ id: 'ins1', policy_name: 'Star Health Plan', provider: 'Star Health', premium: 15000, start_date: '2024-01-01', expiry_date: '2025-01-01' }} />);
    expect(screen.getByDisplayValue('Star Health Plan')).toBeTruthy();
    expect(screen.getByDisplayValue('Star Health')).toBeTruthy();
  });
});
