import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

vi.mock('../services/api', () => ({
  searchStock: vi.fn().mockResolvedValue([]),
  fetchStockPrice: vi.fn().mockResolvedValue({ current_price: 100 }),
  getStockSummary: vi.fn().mockResolvedValue([]),
  getStockHistory: vi.fn().mockResolvedValue({ data: [] }),
}));

vi.mock('html2canvas', () => ({
  default: vi.fn().mockResolvedValue({ toDataURL: () => 'data:image/png;base64,test' }),
}));

import TradePlanner from './BuyPlannerModal';

describe('BuyPlannerModal (TradePlanner)', () => {
  it('renders the Trade Planner title', async () => {
    render(<TradePlanner />);
    await waitFor(() => {
      expect(screen.getByText('Trade Planner')).toBeTruthy();
    });
  });

  it('renders search input', async () => {
    render(<TradePlanner />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Search.*filter stocks/)).toBeTruthy();
    });
  });

  it('renders column headers after loading', async () => {
    const { getStockSummary } = await import('../services/api');
    getStockSummary.mockResolvedValueOnce([]);
    render(<TradePlanner />);
    await waitFor(() => {
      expect(screen.getByText(/Stock/)).toBeTruthy();
    });
  });

  it('renders with stock data', async () => {
    const { getStockSummary } = await import('../services/api');
    getStockSummary.mockResolvedValueOnce([
      {
        symbol: 'RELIANCE', exchange: 'NSE', name: 'Reliance Industries',
        total_held_qty: 10, avg_buy_price: 2500, current_price: 2800,
        unrealized_pl: 3000, unrealized_pl_pct: 12.0,
        held_lots: [{ buy_date: '2024-01-01', quantity: 10, buy_price: 2500 }],
        ltcg_profitable_qty: 5, ltcg_loss_qty: 0, stcg_qty: 5, stcg_profitable_qty: 3, stcg_loss_qty: 2,
        total_invested: 25000, ltcg_invested: 12500, stcg_invested: 12500,
        live: { current_price: 2800, week_52_low: 2000, week_52_high: 3000, day_change_pct: 1.5 },
      },
    ]);
    render(<TradePlanner />);
    await waitFor(() => {
      expect(screen.getByText('RELIANCE')).toBeTruthy();
    });
  });

  it('renders On Hand column header', async () => {
    render(<TradePlanner />);
    await waitFor(() => {
      expect(screen.getByText(/On Hand/)).toBeTruthy();
    });
  });
});
