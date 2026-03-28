import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import StockSummaryTable from './StockSummaryTable';

vi.mock('../services/api', () => ({
  getStockHistory: vi.fn().mockResolvedValue([]),
  getUserSettings: vi.fn().mockResolvedValue({}),
  saveUserSettings: vi.fn().mockResolvedValue({}),
}));

// portfolio is an array of HoldingWithLive objects: { holding: {...}, ... }
const portfolioItems = [
  {
    holding: { id: 'h1', symbol: 'RELIANCE', name: 'Reliance Industries', exchange: 'NSE', quantity: 10, buy_price: 2500, buy_date: '2024-01-15' },
    current_value: 28000, unrealized_pl: 3000, unrealized_pl_pct: 12.0,
  },
  {
    holding: { id: 'h2', symbol: 'TCS', name: 'Tata Consultancy Services', exchange: 'NSE', quantity: 5, buy_price: 3400, buy_date: '2024-03-01' },
    current_value: 16000, unrealized_pl: -1000, unrealized_pl_pct: -5.88,
  },
];

const mockStocks = [
  {
    symbol: 'RELIANCE', name: 'Reliance Industries', exchange: 'NSE',
    quantity: 10, buy_price: 2500, current_price: 2800, buy_date: '2024-01-15',
    gain: 3000, gain_pct: 12.0, num_held_lots: 1, num_sold_lots: 0,
    lots: [],
  },
  {
    symbol: 'TCS', name: 'Tata Consultancy Services', exchange: 'NSE',
    quantity: 5, buy_price: 3400, current_price: 3200, buy_date: '2024-03-01',
    gain: -1000, gain_pct: -5.88, num_held_lots: 1, num_sold_lots: 0,
    lots: [],
  },
];

const defaultProps = {
  stocks: mockStocks,
  loading: false,
  onAddStock: vi.fn(),
  portfolio: portfolioItems,
  onSell: vi.fn(),
  onBulkSell: vi.fn(),
  onDividend: vi.fn(),
  transactions: [],
  onImportContractNote: vi.fn(),
  onImportDividendStatement: vi.fn(),
};

describe('StockSummaryTable', () => {
  it('renders empty state when no stocks', () => {
    render(<StockSummaryTable {...defaultProps} stocks={[]} />);
    expect(screen.getByText('No stocks in your portfolio')).toBeTruthy();
  });

  it('renders stock symbols', () => {
    render(<StockSummaryTable {...defaultProps} />);
    expect(screen.getByText('RELIANCE')).toBeTruthy();
    expect(screen.getByText('TCS')).toBeTruthy();
  });

  it('renders company names', () => {
    render(<StockSummaryTable {...defaultProps} />);
    expect(screen.getByText('Reliance Industries')).toBeTruthy();
  });

  it('shows loading state', () => {
    render(<StockSummaryTable {...defaultProps} stocks={[]} loading={true} />);
    expect(screen.getByText(/Loading stock summary/)).toBeTruthy();
  });
});
