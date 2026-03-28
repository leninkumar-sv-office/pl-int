import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import AddNPSModal from './AddNPSModal';

const defaultProps = {
  onSubmit: vi.fn(),
  onClose: vi.fn(),
};

describe('AddNPSModal', () => {
  it('renders modal title for new account', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Add NPS Account')).toBeTruthy();
  });

  it('renders modal title for edit mode', () => {
    render(<AddNPSModal {...defaultProps} mode="edit" initialData={{ id: 'nps1', account_name: 'NPS Self', start_date: '2024-01-01' }} />);
    expect(screen.getByText('Edit NPS Account')).toBeTruthy();
  });

  it('renders modal title for contribution mode', () => {
    render(<AddNPSModal {...defaultProps} mode="contribution" initialData={{ id: 'nps1', account_name: 'My NPS' }} />);
    expect(screen.getByText(/Add Contribution — My NPS/)).toBeTruthy();
  });

  it('renders Account Name field', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Account Name *')).toBeTruthy();
  });

  it('renders PRAN field', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('PRAN')).toBeTruthy();
  });

  it('renders Tier selector', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Tier *')).toBeTruthy();
    expect(screen.getByDisplayValue('Tier I')).toBeTruthy();
  });

  it('renders Fund Manager dropdown', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Fund Manager')).toBeTruthy();
  });

  it('renders Scheme Preference dropdown', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Scheme Preference')).toBeTruthy();
    expect(screen.getByDisplayValue('Auto Choice')).toBeTruthy();
  });

  it('renders Start Date field', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Start Date *')).toBeTruthy();
  });

  it('renders Status dropdown with default Active', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Status')).toBeTruthy();
    expect(screen.getByDisplayValue('Active')).toBeTruthy();
  });

  it('renders submit button for add mode', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('+ Add NPS')).toBeTruthy();
  });

  it('renders submit button for edit mode', () => {
    render(<AddNPSModal {...defaultProps} mode="edit" initialData={{ id: 'nps1', account_name: 'NPS Self', start_date: '2024-01-01' }} />);
    expect(screen.getByText('Update NPS')).toBeTruthy();
  });

  it('renders submit button for contribution mode', () => {
    render(<AddNPSModal {...defaultProps} mode="contribution" initialData={{ id: 'nps1', account_name: 'My NPS' }} />);
    expect(screen.getByText('+ Add Contribution')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<AddNPSModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders NPS tax benefits info box', () => {
    render(<AddNPSModal {...defaultProps} />);
    expect(screen.getByText(/NPS Tax Benefits/)).toBeTruthy();
  });

  it('shows contribution fields in contribution mode', () => {
    render(<AddNPSModal {...defaultProps} mode="contribution" initialData={{ id: 'nps1', account_name: 'My NPS' }} />);
    expect(screen.getByText('Date *')).toBeTruthy();
    expect(screen.getByText(/Amount/)).toBeTruthy();
    expect(screen.getByText('Remarks')).toBeTruthy();
  });
});
