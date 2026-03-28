import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SellStockModal from './SellStockModal';

const defaultProps = {
  holding: {
    holding: { id: 'h1', symbol: 'RELIANCE', exchange: 'NSE', quantity: 10, buy_price: 2500, buy_date: '2024-01-15' },
    live: { current_price: 2800 },
  },
  onSell: vi.fn(),
  onClose: vi.fn(),
};

describe('SellStockModal', () => {
  it('renders modal title with symbol', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Sell RELIANCE')).toBeTruthy();
  });

  it('renders holding info section', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Holding')).toBeTruthy();
    expect(screen.getByText('Shares Held')).toBeTruthy();
    expect(screen.getByText('Buy Price')).toBeTruthy();
    expect(screen.getByText('Current Price')).toBeTruthy();
  });

  it('renders Shares to Sell field', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Shares to Sell *')).toBeTruthy();
  });

  it('renders Sell Price field', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText(/Sell Price/)).toBeTruthy();
  });

  it('renders Sell Date field', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Sell Date *')).toBeTruthy();
  });

  it('renders Estimated P&L section', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Estimated P&L')).toBeTruthy();
  });

  it('renders submit button with quantity', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Sell 10 Shares')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<SellStockModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('pre-fills quantity with holding quantity', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByDisplayValue('10')).toBeTruthy();
  });

  it('pre-fills sell price with current price', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByDisplayValue('2800')).toBeTruthy();
  });

  it('shows symbol and exchange in holding info', () => {
    render(<SellStockModal {...defaultProps} />);
    expect(screen.getByText('RELIANCE')).toBeTruthy();
    expect(screen.getByText('NSE')).toBeTruthy();
  });
});
