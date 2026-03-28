import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import EditLotModal from './EditLotModal';

const defaultProps = {
  title: 'Edit Held Lot — RELIANCE',
  fields: [
    { key: 'buy_price', label: 'Buy Price', type: 'number', value: 2500, step: '0.01', min: '0.01' },
    { key: 'quantity', label: 'Quantity', type: 'number', value: 10, min: '1' },
    { key: 'buy_date', label: 'Buy Date', type: 'date', value: '2024-01-15' },
  ],
  onSave: vi.fn(),
  onClose: vi.fn(),
};

describe('EditLotModal', () => {
  it('renders modal title', () => {
    render(<EditLotModal {...defaultProps} />);
    expect(screen.getByText('Edit Held Lot — RELIANCE')).toBeTruthy();
  });

  it('renders all field labels', () => {
    render(<EditLotModal {...defaultProps} />);
    expect(screen.getByText('Buy Price')).toBeTruthy();
    expect(screen.getByText('Quantity')).toBeTruthy();
    expect(screen.getByText('Buy Date')).toBeTruthy();
  });

  it('renders field values', () => {
    render(<EditLotModal {...defaultProps} />);
    expect(screen.getByDisplayValue('2500')).toBeTruthy();
    expect(screen.getByDisplayValue('10')).toBeTruthy();
    expect(screen.getByDisplayValue('2024-01-15')).toBeTruthy();
  });

  it('renders Save Changes button', () => {
    render(<EditLotModal {...defaultProps} />);
    expect(screen.getByText('Save Changes')).toBeTruthy();
  });

  it('renders Cancel button', () => {
    render(<EditLotModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when Cancel is clicked', () => {
    const onClose = vi.fn();
    render(<EditLotModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('renders with different title for sold lot', () => {
    render(<EditLotModal {...defaultProps} title="Edit Sold Lot — INFY" />);
    expect(screen.getByText('Edit Sold Lot — INFY')).toBeTruthy();
  });

  it('renders with single field', () => {
    const singleField = {
      ...defaultProps,
      fields: [{ key: 'buy_price', label: 'Buy Price', type: 'number', value: 1500 }],
    };
    render(<EditLotModal {...singleField} />);
    expect(screen.getByText('Buy Price')).toBeTruthy();
    expect(screen.getByDisplayValue('1500')).toBeTruthy();
  });
});
