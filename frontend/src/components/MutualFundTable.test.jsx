import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MutualFundTable from './MutualFundTable';

vi.mock('../services/api', () => ({
  getMFHistory: vi.fn().mockResolvedValue([]),
  updateMFHolding: vi.fn().mockResolvedValue({}),
  updateMFSoldRow: vi.fn().mockResolvedValue({}),
  renameMFund: vi.fn().mockResolvedValue({}),
  getExpiryRules: vi.fn().mockResolvedValue([]),
  saveExpiryRule: vi.fn().mockResolvedValue({}),
  deleteExpiryRule: vi.fn().mockResolvedValue({}),
}));

const mockFunds = [
  {
    fund_code: 'INF846K01EW2',
    name: 'Axis Bluechip Direct Growth',
    total_held_units: 100.5,
    avg_nav: 45.0,
    current_nav: 52.0,
    total_invested: 4522.5,
    current_value: 5226.0,
    unrealized_pl: 703.5,
    unrealized_pl_pct: 15.56,
    realized_pl: 0,
    week_52_low: 40,
    week_52_high: 55,
    day_change_pct: 0.5,
    week_change_pct: 1.2,
    month_change_pct: 3.5,
    sma_200: 48.0,
    signal: 'weak_bull',
    rsi: 55,
    held_lots: [
      { id: 'lot1', buy_date: '2024-01-15', units: 100.5, buy_price: 45.0, pl: 703.5, buy_cost: 4522.5 },
    ],
    _held_lots: [{ buy_date: '2024-01-15', units: 100.5 }],
  },
];

const defaultProps = {
  funds: mockFunds,
  loading: false,
  mfDashboard: null,
  onBuyMF: vi.fn(),
  onRedeemMF: vi.fn(),
  onConfigSIP: vi.fn(),
  sipConfigs: [],
  onImportCDSLCAS: vi.fn(),
};

describe('MutualFundTable', () => {
  it('renders loading state when loading with no funds', () => {
    render(<MutualFundTable {...defaultProps} funds={[]} loading={true} />);
    expect(screen.getByText('Loading mutual fund data...')).toBeTruthy();
  });

  it('renders Mutual Fund Summary title', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText(/Mutual Fund Summary/)).toBeTruthy();
  });

  it('renders funds held badge', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText('1 funds held')).toBeTruthy();
  });

  it('renders profit and loss badges', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText('1 in profit')).toBeTruthy();
    expect(screen.getByText('0 in loss')).toBeTruthy();
  });

  it('renders Import CDSL CAS button', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText('Import CDSL CAS')).toBeTruthy();
  });

  it('renders fund name in table', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText(/Axis Bluechip/)).toBeTruthy();
  });

  it('renders with empty funds array', () => {
    render(<MutualFundTable {...defaultProps} funds={[]} loading={false} />);
    // Should render the section with 0 funds
    expect(screen.getByText(/Mutual Fund Summary/)).toBeTruthy();
  });

  it('renders column header for Units', () => {
    render(<MutualFundTable {...defaultProps} />);
    expect(screen.getByText('Units')).toBeTruthy();
  });
});
