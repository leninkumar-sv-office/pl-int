import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TransactionHistory from './TransactionHistory';

const mockTransactions = [
  {
    id: 'tx1', symbol: 'RELIANCE', name: 'Reliance Industries', exchange: 'NSE',
    quantity: 10, buy_price: 2500, sell_price: 2800,
    buy_date: '2024-01-15', sell_date: '2024-06-15', realized_pl: 3000,
  },
  {
    id: 'tx2', symbol: 'TCS', name: 'Tata Consultancy Services', exchange: 'NSE',
    quantity: 5, buy_price: 3600, sell_price: 3400,
    buy_date: '2024-03-01', sell_date: '2024-08-01', realized_pl: -1000,
  },
];

describe('TransactionHistory', () => {
  it('renders empty state when no transactions', () => {
    render(<TransactionHistory transactions={[]} />);
    expect(screen.getByText('No transactions yet')).toBeTruthy();
  });

  it('renders transaction history title when transactions exist', () => {
    render(<TransactionHistory transactions={mockTransactions} />);
    expect(screen.getByText('Transaction History')).toBeTruthy();
  });

  it('renders sold stock symbols', () => {
    render(<TransactionHistory transactions={mockTransactions} />);
    expect(screen.getByText('RELIANCE')).toBeTruthy();
    expect(screen.getByText('TCS')).toBeTruthy();
  });

  it('renders column headers', () => {
    render(<TransactionHistory transactions={mockTransactions} />);
    expect(screen.getByText('Qty Sold')).toBeTruthy();
    expect(screen.getByText('Buy Price')).toBeTruthy();
    expect(screen.getByText('Sell Price')).toBeTruthy();
    expect(screen.getByText('Realized P&L')).toBeTruthy();
  });

  it('renders total realized P&L badge', () => {
    render(<TransactionHistory transactions={mockTransactions} />);
    expect(screen.getByText(/Total Realized/)).toBeTruthy();
  });

  it('handles null transactions gracefully', () => {
    render(<TransactionHistory transactions={null} />);
    expect(screen.getByText('No transactions yet')).toBeTruthy();
  });
});
