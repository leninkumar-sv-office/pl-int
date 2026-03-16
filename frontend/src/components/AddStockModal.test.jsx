import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AddStockModal from './AddStockModal';

vi.mock('../services/api', () => ({
  lookupStockName: vi.fn().mockResolvedValue({ name: '' }),
}));

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
};

describe('AddStockModal', () => {
  it('renders modal title', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Add Stock to Portfolio')).toBeTruthy();
  });

  it('renders Stock Symbol field', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Stock Symbol *')).toBeTruthy();
  });

  it('renders Exchange selector', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Exchange')).toBeTruthy();
    expect(screen.getByDisplayValue('NSE')).toBeTruthy();
  });

  it('renders Quantity field', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Quantity *')).toBeTruthy();
  });

  it('renders Buy Price field', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText(/Buy Price/)).toBeTruthy();
  });

  it('renders Buy Date field', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Buy Date *')).toBeTruthy();
  });

  it('renders submit button', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('+ Add Stock')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddStockModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('pre-fills symbol from initialData', () => {
    render(<AddStockModal {...defaultProps} initialData={{ symbol: 'INFY', exchange: 'NSE' }} />);
    const symbolInput = screen.getByPlaceholderText('e.g. RELIANCE');
    expect(symbolInput.value).toBe('INFY');
  });
});
