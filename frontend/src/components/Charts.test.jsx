import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Charts from './Charts';

const mockPortfolio = [
  {
    holding: { symbol: 'RELIANCE', buy_price: 2500, quantity: 10, buy_date: '2024-01-15' },
    live: { current_price: 2800, week_52_low: 2000, week_52_high: 3000 },
    unrealized_pl: 3000,
    current_value: 28000,
    is_above_buy_price: true,
  },
  {
    holding: { symbol: 'INFY', buy_price: 1400, quantity: 5, buy_date: '2024-03-01' },
    live: { current_price: 1600, week_52_low: 1200, week_52_high: 1800 },
    unrealized_pl: 1000,
    current_value: 8000,
    is_above_buy_price: true,
  },
];

const mockSummary = {
  unrealized_pl: 4000,
  realized_pl: 1500,
  total_invested: 32000,
  total_current: 36000,
};

const mockTransactions = [
  { symbol: 'RELIANCE', action: 'buy', quantity: 10, price: 2500, date: '2024-01-15' },
];

describe('Charts', () => {
  it('renders empty state when no portfolio data', () => {
    render(<Charts portfolio={[]} summary={null} transactions={[]} />);
    expect(screen.getByText('No data for charts')).toBeTruthy();
  });

  it('renders empty state with null portfolio', () => {
    render(<Charts portfolio={null} summary={null} transactions={null} />);
    expect(screen.getByText('No data for charts')).toBeTruthy();
  });

  it('renders chart sections with portfolio data', () => {
    render(<Charts portfolio={mockPortfolio} summary={mockSummary} transactions={mockTransactions} />);
    expect(screen.getByText('Unrealized P&L by Stock')).toBeTruthy();
  });

  it('renders portfolio composition chart section', () => {
    render(<Charts portfolio={mockPortfolio} summary={mockSummary} transactions={mockTransactions} />);
    expect(screen.getByText('Portfolio Composition')).toBeTruthy();
  });

  it('renders 52-week range chart section', () => {
    render(<Charts portfolio={mockPortfolio} summary={mockSummary} transactions={mockTransactions} />);
    expect(screen.getByText(/52-Week Position/)).toBeTruthy();
  });

  it('renders when summary has negative PL', () => {
    const lossSummary = { ...mockSummary, unrealized_pl: -2000, realized_pl: -500 };
    render(<Charts portfolio={mockPortfolio} summary={lossSummary} transactions={mockTransactions} />);
    expect(screen.getByText('Unrealized P&L by Stock')).toBeTruthy();
  });

  it('does not crash with empty transactions', () => {
    render(<Charts portfolio={mockPortfolio} summary={mockSummary} transactions={[]} />);
    expect(screen.getByText('Unrealized P&L by Stock')).toBeTruthy();
  });
});
