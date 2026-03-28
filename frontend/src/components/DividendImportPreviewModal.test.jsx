import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DividendImportPreviewModal from './DividendImportPreviewModal';

const mockData = {
  statement_period: 'Jan 2024 - Mar 2024',
  dividends: [
    { date: '2024-01-15', symbol: 'RELIANCE', company_raw: 'Reliance Industries Ltd', amount: 500, symbol_matched: true },
    { date: '2024-02-20', symbol: 'INFY', company_raw: 'Infosys Ltd', amount: 300, symbol_matched: true },
  ],
  summary: { count: 2, total_amount: 800, matched: 2, unmatched: 0 },
};

const defaultProps = {
  data: mockData,
  existingSymbols: new Set(['RELIANCE', 'INFY']),
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

describe('DividendImportPreviewModal', () => {
  it('renders null when data is null', () => {
    const { container } = render(<DividendImportPreviewModal {...defaultProps} data={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders modal title', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Dividend Import Preview')).toBeTruthy();
  });

  it('renders statement period', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Jan 2024 - Mar 2024/)).toBeTruthy();
  });

  it('renders matched count badge', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('2 matched')).toBeTruthy();
  });

  it('renders table column headers', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Date')).toBeTruthy();
    expect(screen.getByText('Symbol')).toBeTruthy();
    expect(screen.getByText('Company (from PDF)')).toBeTruthy();
    expect(screen.getByText('Amount')).toBeTruthy();
    expect(screen.getByText('Status')).toBeTruthy();
  });

  it('renders confirm button', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Confirm Import/)).toBeTruthy();
  });

  it('renders cancel button', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeTruthy();
  });

  it('shows OK status for matched symbols', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    const okBadges = screen.getAllByText('OK');
    expect(okBadges.length).toBe(2);
  });

  it('shows unmatched count when unmatched dividends exist', () => {
    const unmatchedData = {
      ...mockData,
      dividends: [
        ...mockData.dividends,
        { date: '2024-03-10', symbol: 'UNKNOWN', company_raw: 'Unknown Corp', amount: 100, symbol_matched: false },
      ],
      summary: { count: 3, total_amount: 900, matched: 2, unmatched: 1 },
    };
    render(<DividendImportPreviewModal {...defaultProps} data={unmatchedData} />);
    expect(screen.getByText('1 unmatched')).toBeTruthy();
  });

  it('shows duplicate badge when duplicates exist', () => {
    const dupData = {
      ...mockData,
      dividends: [
        ...mockData.dividends,
        { date: '2024-01-15', symbol: 'RELIANCE', company_raw: 'Reliance Industries Ltd', amount: 500, symbol_matched: true, isDuplicate: true },
      ],
      summary: { count: 3, total_amount: 1300, matched: 3, unmatched: 0 },
    };
    render(<DividendImportPreviewModal {...defaultProps} data={dupData} />);
    const dupTexts = screen.getAllByText(/duplicate/);
    expect(dupTexts.length).toBeGreaterThanOrEqual(1);
  });

  it('renders total row', () => {
    render(<DividendImportPreviewModal {...defaultProps} />);
    expect(screen.getByText(/Total \(excl\. duplicates\)/)).toBeTruthy();
    expect(screen.getByText('2 to import')).toBeTruthy();
  });
});
