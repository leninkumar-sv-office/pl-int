import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SIPConfigModal from './SIPConfigModal';

const defaultProps = {
  fund: {
    fund_code: 'INF846K01EW2',
    name: 'Axis Bluechip Direct Growth',
    current_nav: 52.0,
  },
  existingSIP: null,
  onSave: vi.fn(),
  onDelete: vi.fn(),
  onClose: vi.fn(),
};

describe('SIPConfigModal', () => {
  it('renders Setup SIP title for new SIP', () => {
    render(<SIPConfigModal {...defaultProps} />);
    const elements = screen.getAllByText('Setup SIP');
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders Edit SIP title for existing SIP', () => {
    render(<SIPConfigModal {...defaultProps} existingSIP={{ amount: 5000, frequency: 'monthly', sip_date: 1, start_date: '2024-01-01', enabled: true }} />);
    expect(screen.getByText('Edit SIP')).toBeTruthy();
  });

  it('renders fund name in info section', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Fund')).toBeTruthy();
    expect(screen.getByText('Axis Bluechip')).toBeTruthy();
  });

  it('renders SIP Amount field', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText(/SIP Amount/)).toBeTruthy();
  });

  it('renders Frequency dropdown', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Frequency *')).toBeTruthy();
    expect(screen.getByDisplayValue('Monthly')).toBeTruthy();
  });

  it('renders Day of Month field', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Day of Month *')).toBeTruthy();
  });

  it('renders Start Date field', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Start Date')).toBeTruthy();
  });

  it('renders End Date field', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('End Date (optional)')).toBeTruthy();
  });

  it('renders Enabled checkbox', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Enabled')).toBeTruthy();
  });

  it('renders Notes field', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Notes')).toBeTruthy();
  });

  it('renders Setup SIP submit button for new', () => {
    render(<SIPConfigModal {...defaultProps} />);
    const submitBtn = screen.getAllByText('Setup SIP').find(el => el.tagName === 'BUTTON' && el.type === 'submit');
    expect(submitBtn).toBeTruthy();
  });

  it('renders Update SIP submit button for edit', () => {
    render(<SIPConfigModal {...defaultProps} existingSIP={{ amount: 5000, frequency: 'monthly', sip_date: 1, start_date: '2024-01-01', enabled: true }} />);
    expect(screen.getByText('Update SIP')).toBeTruthy();
  });

  it('renders Delete SIP button for edit mode', () => {
    render(<SIPConfigModal {...defaultProps} existingSIP={{ amount: 5000, frequency: 'monthly', sip_date: 1, start_date: '2024-01-01', enabled: true }} />);
    expect(screen.getByText('Delete SIP')).toBeTruthy();
  });

  it('does not render Delete SIP button for new SIP', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.queryByText('Delete SIP')).toBeNull();
  });

  it('renders cancel button', () => {
    render(<SIPConfigModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('calls onClose when cancel is clicked', () => {
    const onClose = vi.fn();
    render(<SIPConfigModal {...defaultProps} onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalled();
  });

  it('shows next SIP date for existing SIP', () => {
    render(<SIPConfigModal {...defaultProps} existingSIP={{ amount: 5000, frequency: 'monthly', sip_date: 1, start_date: '2024-01-01', enabled: true, next_sip_date: '2024-04-01' }} />);
    expect(screen.getByText('Next SIP Date')).toBeTruthy();
    expect(screen.getByText('2024-04-01')).toBeTruthy();
  });
});
