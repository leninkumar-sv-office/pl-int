import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DividendModal from './DividendModal';

const defaultProps = {
  symbol: 'RELIANCE',
  exchange: 'NSE',
  onSubmit: vi.fn(),
  onClose: vi.fn(),
};

describe('DividendModal', () => {
  it('renders modal title with symbol', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText(/Record Dividend — RELIANCE/)).toBeTruthy();
  });

  it('renders Dividend Amount field', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText(/Dividend Amount/)).toBeTruthy();
  });

  it('renders Date field', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText('Date')).toBeTruthy();
  });

  it('renders Remarks field', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText(/Remarks/)).toBeTruthy();
  });

  it('renders amount placeholder', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByPlaceholderText('e.g. 500.00')).toBeTruthy();
  });

  it('renders remarks placeholder', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByPlaceholderText('e.g. Interim dividend Q3')).toBeTruthy();
  });

  it('renders submit button', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText('Record Dividend')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<DividendModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<DividendModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('disables submit button when amount is empty', () => {
    render(<DividendModal {...defaultProps} />);
    const btn = screen.getByText('Record Dividend');
    expect(btn.disabled).toBe(true);
  });

  it('renders close button (x)', () => {
    render(<DividendModal {...defaultProps} />);
    const closeBtn = screen.getByText('\u00D7');
    expect(closeBtn).toBeTruthy();
  });
});
