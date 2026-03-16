import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Dashboard from './Dashboard';

const baseSummary = {
  total_invested: 100000,
  current_value: 120000,
  unrealized_pl: 20000,
  realized_pl: 5000,
  stocks_in_profit: 8,
  stocks_in_loss: 2,
  total_holdings: 10,
  total_dividend: 1000,
};

describe('Dashboard', () => {
  it('renders null when no summary and not loading', () => {
    const { container } = render(<Dashboard summary={null} loading={false} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders Portfolio Summary toggle button', () => {
    render(<Dashboard summary={baseSummary} loading={false} />);
    expect(screen.getByText('Portfolio Summary')).toBeTruthy();
  });

  it('shows loading state when loading and no summary', () => {
    render(<Dashboard summary={null} loading={true} />);
    expect(screen.getByText('Portfolio Summary')).toBeTruthy();
  });

  it('renders summary cards when expanded', () => {
    localStorage.setItem('dashboardExpanded', 'true');
    render(<Dashboard summary={baseSummary} loading={false} />);
    expect(screen.getByText('Total Invested')).toBeTruthy();
    expect(screen.getByText('Current Value')).toBeTruthy();
    expect(screen.getByText('Unrealized P&L')).toBeTruthy();
  });

  it('renders collapsed summary inline when not expanded', () => {
    localStorage.setItem('dashboardExpanded', 'false');
    render(<Dashboard summary={baseSummary} loading={false} />);
    // The collapsed summary includes current value text
    expect(screen.getByText('Portfolio Summary')).toBeTruthy();
  });

  it('renders with mfDashboard data', () => {
    localStorage.setItem('dashboardExpanded', 'true');
    const mfDashboard = {
      total_invested: 50000,
      current_value: 60000,
      unrealized_pl: 10000,
      realized_pl: 0,
      funds_in_profit: 5,
      funds_in_loss: 1,
      total_funds: 6,
    };
    render(<Dashboard summary={baseSummary} mfDashboard={mfDashboard} loading={false} />);
    expect(screen.getByText('Total Invested')).toBeTruthy();
  });

  it('renders with zero values gracefully', () => {
    const zeroSummary = {
      total_invested: 0,
      current_value: 0,
      unrealized_pl: 0,
      realized_pl: 0,
      stocks_in_profit: 0,
      stocks_in_loss: 0,
      total_holdings: 0,
      total_dividend: 0,
    };
    localStorage.setItem('dashboardExpanded', 'true');
    render(<Dashboard summary={zeroSummary} loading={false} />);
    expect(screen.getByText('Total Invested')).toBeTruthy();
  });
});
