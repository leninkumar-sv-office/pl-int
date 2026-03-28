import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ImportPreviewModal from './ImportPreviewModal';

const mockData = {
  trade_date: '2024-03-15',
  contract_no: 'CN12345',
  transactions: [
    { action: 'Buy', symbol: 'RELIANCE', name: 'Reliance Industries', isin: 'INE002A01018', quantity: 10, wap: 2500, effective_price: 2510, net_total_after_levies: 25100, trade_date: '2024-03-15' },
    { action: 'Sell', symbol: 'INFY', name: 'Infosys', isin: 'INE009A01021', quantity: 5, wap: 1400, effective_price: 1395, net_total_after_levies: 6975, trade_date: '2024-03-15' },
  ],
  summary: { buys: 1, sells: 1, total_cost: 25100, total_proceeds: 6975 },
};

const defaultProps = {
  data: mockData,
  existingSymbols: new Set(['RELIANCE', 'INFY']),
  stockSummary: [{ symbol: 'INFY', avg_buy_price: 1300 }],
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe('ImportPreviewModal', () => {
  it('renders null when data is null', () => {
    const { container } = render(<ImportPreviewModal {...defaultProps} data={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders Contract Note Preview title', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Contract Note Preview')).toBeTruthy();
  });

  it('renders trade date and contract number', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Trade Date: 2024-03-15/)).toBeTruthy();
    expect(screen.getByText(/CN12345/)).toBeTruthy();
  });

  it('renders buy and sell count badges', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('1 Buys')).toBeTruthy();
    expect(screen.getByText('1 Sells')).toBeTruthy();
  });

  it('renders BUY Transactions section', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/BUY Transactions/)).toBeTruthy();
  });

  it('renders SELL Transactions section', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/SELL Transactions/)).toBeTruthy();
  });

  it('renders confirm import button', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Confirm Import/)).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders Net Obligation', () => {
    render(<ImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Net Obligation/)).toBeTruthy();
  });

  it('shows duplicate count when duplicates exist', () => {
    const dupData = {
      ...mockData,
      transactions: [
        ...mockData.transactions,
        { action: 'Buy', symbol: 'TCS', name: 'TCS', isin: 'INE467B01029', quantity: 3, wap: 3000, effective_price: 3010, net_total_after_levies: 9030, isDuplicate: true, trade_date: '2024-03-15' },
      ],
      summary: { buys: 2, sells: 1, total_cost: 34130, total_proceeds: 6975 },
    };
    render(<ImportPreviewModal {...defaultProps} data={dupData} />);
    expect(screen.getByText(/1 Duplicate/)).toBeTruthy();
  });

  it('shows new symbol badge for unknown symbols', () => {
    const newSymbolData = {
      ...mockData,
      transactions: [
        { action: 'Buy', symbol: 'NEWSTOCK', name: 'New Stock Corp', isin: 'INE999A01099', quantity: 2, wap: 500, effective_price: 505, net_total_after_levies: 1010, trade_date: '2024-03-15' },
      ],
      summary: { buys: 1, sells: 0, total_cost: 1010, total_proceeds: 0 },
    };
    render(<ImportPreviewModal {...defaultProps} data={newSymbolData} existingSymbols={new Set()} />);
    expect(screen.getByText('NEW')).toBeTruthy();
  });
});
