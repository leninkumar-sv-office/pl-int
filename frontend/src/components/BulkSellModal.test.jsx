import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import BulkSellModal from './BulkSellModal';

const makeItem = (symbol, exchange, quantity, buyPrice, currentPrice) => ({
  holding: { id: `h-${symbol}`, symbol, exchange, name: symbol, quantity, buy_price: buyPrice },
  live: { current_price: currentPrice },
});

const defaultProps = {
  items: [
    makeItem('RELIANCE', 'NSE', 10, 2500, 2800),
    makeItem('INFY', 'NSE', 5, 1400, 1600),
  ],
  onSell: vi.fn(),
  onClose: vi.fn(),
};

describe('BulkSellModal', () => {
  it('renders modal title with lot and stock counts', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText(/Bulk Sell/)).toBeTruthy();
    expect(screen.getByText(/2 Lots across 2 Stocks/)).toBeTruthy();
  });

  it('renders Stock column header', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Stock')).toBeTruthy();
  });

  it('renders Qty column header', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Qty')).toBeTruthy();
  });

  it('renders stock symbols in table', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('RELIANCE')).toBeTruthy();
    expect(screen.getByText('INFY')).toBeTruthy();
  });

  it('renders Sell Date field', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Sell Date *')).toBeTruthy();
  });

  it('renders summary section with stocks count', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Stocks')).toBeTruthy();
    expect(screen.getByText('Total Lots')).toBeTruthy();
    expect(screen.getByText('Total Qty')).toBeTruthy();
    expect(screen.getByText('Total Invested')).toBeTruthy();
    expect(screen.getByText('Estimated P&L')).toBeTruthy();
  });

  it('renders sell button with total qty', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Sell All 15 Shares')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<BulkSellModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders sell price inputs for each stock', () => {
    render(<BulkSellModal {...defaultProps} />);
    const inputs = screen.getAllByDisplayValue('2800');
    expect(inputs.length).toBeGreaterThanOrEqual(1);
  });

  it('handles single lot correctly', () => {
    const singleProps = {
      items: [makeItem('TCS', 'NSE', 3, 3000, 3500)],
      onSell: vi.fn(),
      onClose: vi.fn(),
    };
    render(<BulkSellModal {...singleProps} />);
    expect(screen.getByText(/1 Lot across 1 Stock/)).toBeTruthy();
    expect(screen.getByText('Sell All 3 Shares')).toBeTruthy();
  });
});
