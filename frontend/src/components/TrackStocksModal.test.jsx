import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import TrackStocksModal from './TrackStocksModal';

vi.mock('../services/api', () => ({
  searchUntracked: vi.fn().mockResolvedValue([]),
  trackStocks: vi.fn().mockResolvedValue({ count: 1 }),
  lookupStockName: vi.fn().mockResolvedValue({ name: 'Reliance Industries' }),
}));

vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const defaultProps = {
  onClose: vi.fn(),
  onAdded: vi.fn(),
};

describe('TrackStocksModal', () => {
  it('renders modal title', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText('Add to Watchlist')).toBeTruthy();
  });

  it('renders description text', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText(/Search stocks not in your portfolio/)).toBeTruthy();
  });

  it('renders search input', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByPlaceholderText('Search by symbol or company name...')).toBeTruthy();
  });

  it('renders manual symbol input', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByPlaceholderText('Symbol (e.g. RELIANCE)')).toBeTruthy();
  });

  it('renders exchange selector', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByDisplayValue('NSE')).toBeTruthy();
  });

  it('renders + Add button for manual add', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText('+ Add')).toBeTruthy();
  });

  it('renders empty state message', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText('Type to search NSE/BSE stocks')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('renders add to watchlist button (disabled with 0 selected)', () => {
    render(<TrackStocksModal {...defaultProps} />);
    expect(screen.getByText('Add 0 to Watchlist')).toBeTruthy();
  });
});
