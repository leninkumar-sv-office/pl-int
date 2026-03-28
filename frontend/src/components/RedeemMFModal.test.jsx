import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RedeemMFModal from './RedeemMFModal';

const defaultProps = {
  fund: {
    fund_code: 'INF846K01EW2',
    name: 'Axis Bluechip Direct Growth',
    current_nav: 52.0,
    total_held_units: 100.5,
    avg_nav: 45.0,
  },
  onRedeem: vi.fn(),
  onClose: vi.fn(),
};

describe('RedeemMFModal', () => {
  it('renders modal title with fund name', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText(/Redeem Axis Bluechip/)).toBeTruthy();
  });

  it('renders Fund info section', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Fund')).toBeTruthy();
    expect(screen.getByText('Units Held')).toBeTruthy();
    expect(screen.getByText('Avg NAV')).toBeTruthy();
    expect(screen.getByText('Current NAV')).toBeTruthy();
  });

  it('renders Units to Redeem field', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Units to Redeem *')).toBeTruthy();
  });

  it('renders Redemption NAV field', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText(/Redemption NAV/)).toBeTruthy();
  });

  it('renders Redemption Date field', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Redemption Date *')).toBeTruthy();
  });

  it('renders Estimated Amount', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Estimated Amount')).toBeTruthy();
  });

  it('renders Estimated P&L section', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Estimated P&L')).toBeTruthy();
  });

  it('renders submit button with units', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText(/Redeem.*Units/)).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<RedeemMFModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('pre-fills units with total held units', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByDisplayValue('100.5')).toBeTruthy();
  });

  it('pre-fills NAV with current nav', () => {
    render(<RedeemMFModal {...defaultProps} />);
    expect(screen.getByDisplayValue('52')).toBeTruthy();
  });
});
