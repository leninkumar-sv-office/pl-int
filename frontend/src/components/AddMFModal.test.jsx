import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AddMFModal from './AddMFModal';

vi.mock('../services/api', () => ({
  searchMFInstruments: vi.fn().mockResolvedValue([]),
}));

const defaultProps = {
  onAdd: vi.fn(),
  onClose: vi.fn(),
  funds: [],
};

describe('AddMFModal', () => {
  it('renders modal title', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Buy Mutual Fund')).toBeTruthy();
  });

  it('renders NAV field', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText(/NAV/)).toBeTruthy();
  });

  it('renders Units field', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Units *')).toBeTruthy();
  });

  it('renders Buy Date field', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Buy Date *')).toBeTruthy();
  });

  it('renders Search Fund field when no existing fund', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Search Fund *')).toBeTruthy();
  });

  it('renders fund search input', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByPlaceholderText(/Type fund name/)).toBeTruthy();
  });

  it('renders Direct/Regular plan filter buttons', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Direct')).toBeTruthy();
    expect(screen.getByText('Regular')).toBeTruthy();
  });

  it('renders Growth/IDCW type filter buttons', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Growth')).toBeTruthy();
    expect(screen.getByText('IDCW')).toBeTruthy();
  });

  it('renders submit button', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('+ Buy MF')).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<AddMFModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('shows existing fund selector when funds prop provided', () => {
    const funds = [
      { fund_code: 'INF846K01EW2', name: 'Axis Bluechip Direct Growth', current_nav: 52.0 },
    ];
    render(<AddMFModal {...defaultProps} funds={funds} />);
    expect(screen.getByText('Select Existing Fund')).toBeTruthy();
  });

  it('renders fund name field as disabled when initialData has fund_code', () => {
    render(<AddMFModal {...defaultProps} initialData={{ fund_code: 'INF846K01EW2', fund_name: 'Axis Bluechip Direct Growth' }} />);
    expect(screen.getByText('Fund Name')).toBeTruthy();
    const input = screen.getByDisplayValue('Axis Bluechip Direct Growth');
    expect(input.disabled).toBe(true);
  });
});
