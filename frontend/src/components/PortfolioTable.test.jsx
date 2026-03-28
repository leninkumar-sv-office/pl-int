import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PortfolioTable from './PortfolioTable';

const mockPortfolio = [
  {
    holding: { id: 'h1', symbol: 'RELIANCE', exchange: 'NSE', name: 'Reliance Industries', buy_price: 2500, quantity: 10, buy_date: '2024-01-15' },
    live: { current_price: 2800, week_52_low: 2000, week_52_high: 3000, day_change: 50, day_change_pct: 1.82 },
    unrealized_pl: 3000,
    unrealized_pl_pct: 12.0,
    current_value: 28000,
    is_above_buy_price: true,
  },
  {
    holding: { id: 'h2', symbol: 'INFY', exchange: 'NSE', name: 'Infosys', buy_price: 1600, quantity: 5, buy_date: '2024-03-01' },
    live: { current_price: 1400, week_52_low: 1200, week_52_high: 1800, day_change: -20, day_change_pct: -1.41 },
    unrealized_pl: -1000,
    unrealized_pl_pct: -12.5,
    current_value: 7000,
    is_above_buy_price: false,
  },
];

const defaultProps = {
  portfolio: mockPortfolio,
  loading: false,
  onSell: vi.fn(),
  onAddStock: vi.fn(),
};

describe('PortfolioTable', () => {
  it('renders loading state', () => {
    render(<PortfolioTable portfolio={[]} loading={true} onSell={vi.fn()} onAddStock={vi.fn()} />);
    expect(screen.getByText('Loading portfolio...')).toBeTruthy();
  });

  it('renders empty state when portfolio is empty', () => {
    render(<PortfolioTable portfolio={[]} loading={false} onSell={vi.fn()} onAddStock={vi.fn()} />);
    expect(screen.getByText('No stocks in your portfolio')).toBeTruthy();
  });

  it('renders add first stock button in empty state', () => {
    const onAddStock = vi.fn();
    render(<PortfolioTable portfolio={[]} loading={false} onSell={vi.fn()} onAddStock={onAddStock} />);
    const btn = screen.getByText('+ Add Your First Stock');
    fireEvent.click(btn);
    expect(onAddStock).toHaveBeenCalled();
  });

  it('renders Your Holdings title', () => {
    render(<PortfolioTable {...defaultProps} />);
    expect(screen.getByText('Your Holdings')).toBeTruthy();
  });

  it('renders profit and loss count badges', () => {
    render(<PortfolioTable {...defaultProps} />);
    expect(screen.getByText('1 in profit')).toBeTruthy();
    expect(screen.getByText('1 in loss')).toBeTruthy();
  });

  it('renders table column headers', () => {
    render(<PortfolioTable {...defaultProps} />);
    expect(screen.getByText('Stock')).toBeTruthy();
    expect(screen.getByText('Qty')).toBeTruthy();
    expect(screen.getByText('Buy Price')).toBeTruthy();
    expect(screen.getByText('Current Price')).toBeTruthy();
    expect(screen.getByText('52-Week Range')).toBeTruthy();
    expect(screen.getByText('Invested')).toBeTruthy();
    expect(screen.getByText('Current Value')).toBeTruthy();
    expect(screen.getByText('P&L')).toBeTruthy();
  });

  it('renders stock symbols', () => {
    render(<PortfolioTable {...defaultProps} />);
    expect(screen.getByText('RELIANCE')).toBeTruthy();
    expect(screen.getByText('INFY')).toBeTruthy();
  });

  it('renders sell buttons', () => {
    render(<PortfolioTable {...defaultProps} />);
    const sellButtons = screen.getAllByText('Sell');
    expect(sellButtons.length).toBe(2);
  });
});
