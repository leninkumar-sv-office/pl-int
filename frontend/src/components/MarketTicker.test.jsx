import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MarketTicker from './MarketTicker';

vi.mock('../services/api', () => ({
  getTickerHistory: vi.fn().mockResolvedValue([]),
}));

const positiveTicker = { key: 'SENSEX', label: 'Sensex', price: 75000, change: 500, change_pct: 0.67, type: 'index' };
const negativeTicker = { key: 'NIFTY50', label: 'Nifty 50', price: 23000, change: -150, change_pct: -0.66, type: 'index' };
const commodityTicker = { key: 'GOLD', label: 'Gold', price: 60000, change: 200, change_pct: 0.33, type: 'commodity' };

describe('MarketTicker', () => {
  it('returns null when no tickers and not loading', () => {
    const { container } = render(<MarketTicker tickers={[]} loading={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('shows loading message when loading with no tickers', () => {
    render(<MarketTicker tickers={[]} loading={true} />);
    expect(screen.getByText('Loading market data...')).toBeTruthy();
  });

  it('renders ticker label', () => {
    render(<MarketTicker tickers={[positiveTicker]} loading={false} />);
    expect(screen.getByText('Sensex')).toBeTruthy();
  });

  it('renders ticker price', () => {
    render(<MarketTicker tickers={[positiveTicker]} loading={false} />);
    expect(screen.getByText(/75,000/)).toBeTruthy();
  });

  it('renders multiple tickers', () => {
    render(<MarketTicker tickers={[positiveTicker, negativeTicker]} loading={false} />);
    expect(screen.getByText('Sensex')).toBeTruthy();
    expect(screen.getByText('Nifty 50')).toBeTruthy();
  });

  it('renders commodity ticker with rupee prefix', () => {
    render(<MarketTicker tickers={[commodityTicker]} loading={false} />);
    expect(screen.getByText('Gold')).toBeTruthy();
    expect(screen.getByText(/60,000/)).toBeTruthy();
  });

  it('renders zero price as dashes', () => {
    const zeroTicker = { key: 'TEST', label: 'Test', price: 0, change: 0, change_pct: 0, type: 'index' };
    render(<MarketTicker tickers={[zeroTicker]} loading={false} />);
    expect(screen.getByText('--')).toBeTruthy();
  });
});
