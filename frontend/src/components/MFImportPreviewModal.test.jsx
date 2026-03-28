import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MFImportPreviewModal from './MFImportPreviewModal';

const mockData = {
  cas_id: 'CAS123',
  statement_period: '01-Jan-2024 to 31-Mar-2024',
  source: 'CDSL',
  funds: [
    {
      fund_name: 'Axis Bluechip Direct Growth',
      isin: 'INF846K01EW2',
      amc: 'Axis Mutual Fund',
      folio: '1234567',
      fund_code: 'INF846K01EW2',
      scheme_code: 'AXIS001',
      is_new_fund: false,
      transactions: [
        { date: '2024-01-15', action: 'Buy', description: 'Purchase SIP', amount: 5000, nav: 45.5, units: 109.89, balance_units: 109.89 },
        { date: '2024-02-15', action: 'Buy', description: 'Purchase SIP', amount: 5000, nav: 46.2, units: 108.22, balance_units: 218.11 },
      ],
    },
  ],
  summary: { total_purchases: 2, total_redemptions: 0, funds_count: 1, total_invested: 10000 },
};

const defaultProps = {
  data: mockData,
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe('MFImportPreviewModal', () => {
  it('renders null when data is null', () => {
    const { container } = render(<MFImportPreviewModal {...defaultProps} data={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders CDSL CAS Import Preview title', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('CDSL CAS Import Preview')).toBeTruthy();
  });

  it('renders statement period', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/01-Jan-2024 to 31-Mar-2024/)).toBeTruthy();
  });

  it('renders CAS ID', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/CAS123/)).toBeTruthy();
  });

  it('renders buy count badge', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('2 Buys')).toBeTruthy();
  });

  it('renders funds count badge', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('1 Funds')).toBeTruthy();
  });

  it('renders AMC section header', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Axis Mutual Fund')).toBeTruthy();
  });

  it('renders fund name', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Axis Bluechip Direct Growth')).toBeTruthy();
  });

  it('renders table column headers', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Date')).toBeTruthy();
    expect(screen.getByText('Type')).toBeTruthy();
    expect(screen.getByText('Description')).toBeTruthy();
    expect(screen.getByText('NAV')).toBeTruthy();
    expect(screen.getByText('Units')).toBeTruthy();
  });

  it('renders confirm button', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Confirm Import/)).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('shows transaction count per fund', () => {
    render(<MFImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('2 txns')).toBeTruthy();
  });

  it('shows duplicate count when duplicates exist', () => {
    const dupData = {
      ...mockData,
      funds: [{
        ...mockData.funds[0],
        transactions: [
          ...mockData.funds[0].transactions,
          { date: '2024-01-15', action: 'Buy', description: 'Dup SIP', amount: 5000, nav: 45.5, units: 109.89, balance_units: 109.89, isDuplicate: true },
        ],
      }],
    };
    render(<MFImportPreviewModal {...defaultProps} data={dupData} />);
    expect(screen.getByText(/1 Duplicate/)).toBeTruthy();
  });

  it('shows new fund badge for new funds', () => {
    const newFundData = {
      ...mockData,
      funds: [{
        ...mockData.funds[0],
        is_new_fund: true,
      }],
    };
    render(<MFImportPreviewModal {...defaultProps} data={newFundData} />);
    expect(screen.getByText('NEW FUND')).toBeTruthy();
  });
});
