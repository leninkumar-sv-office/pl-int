import React, { useState } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatDate = (dateStr) => {
  if (!dateStr) return '--';
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d.getTime())) return dateStr;
  const dd = String(d.getDate()).padStart(2, '0');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${dd}-${months[d.getMonth()]}-${d.getFullYear()}`;
};

const thStyle = {
  padding: '6px 10px',
  fontSize: '11px',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textAlign: 'left',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

const tdStyle = {
  padding: '7px 10px',
  fontSize: '12px',
  color: 'var(--text)',
};

const dupRowBg = 'rgba(251,191,36,0.10)';
const dupRowBorder = '1px solid rgba(251,191,36,0.25)';

export default function MFImportPreviewModal({ data, onConfirm, onCancel }) {
  const [confirming, setConfirming] = useState(false);

  if (!data) return null;

  const { folio, statement_period, funds, summary } = data;

  // Count importable vs duplicate
  const allTx = funds.flatMap(f => f.transactions);
  const importable = allTx.filter(t => !t.isDuplicate);
  const dupCount = allTx.filter(t => t.isDuplicate).length;

  const handleConfirm = async () => {
    if (importable.length === 0) return;
    setConfirming(true);
    try {
      // Pass only non-duplicate transactions
      const payload = funds.map(f => ({
        ...f,
        transactions: f.transactions.filter(t => !t.isDuplicate),
      })).filter(f => f.transactions.length > 0);
      await onConfirm(payload);
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: '20px',
    }} onClick={onCancel}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', maxWidth: '1000px', width: '100%',
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
      }} onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div style={{
          padding: '16px 20px', borderBottom: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text)' }}>
              SBI MF Statement Preview
              {data._fileCount > 1 && (
                <span style={{
                  marginLeft: '10px', fontSize: '11px', fontWeight: 600,
                  color: 'var(--blue)', background: 'rgba(59,130,246,0.12)',
                  padding: '2px 8px', borderRadius: '8px', verticalAlign: 'middle',
                }}>
                  {data._fileCount} PDFs
                </span>
              )}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Folio: {folio} &nbsp;|&nbsp; Period: {statement_period}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
              background: 'var(--green-bg)', color: 'var(--green)',
            }}>
              {summary.total_purchases} Buys
            </span>
            {summary.total_redemptions > 0 && (
              <span style={{
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: 'var(--red-bg)', color: 'var(--red)',
              }}>
                {summary.total_redemptions} Sells
              </span>
            )}
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
              background: 'rgba(59,130,246,0.12)', color: 'var(--blue)',
            }}>
              {summary.funds_count} Funds
            </span>
            {dupCount > 0 && (
              <span style={{
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: 'rgba(251,191,36,0.15)', color: '#d97706',
              }}>
                {dupCount} Duplicate{dupCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          {funds.map((fund, fi) => (
            <div key={fi} style={{ marginBottom: fi < funds.length - 1 ? '24px' : '0' }}>
              {/* Fund section header */}
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                marginBottom: '8px', paddingBottom: '6px', borderBottom: '1px solid var(--border)',
              }}>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                    {fund.fund_name}
                    {fund.is_new_fund && (
                      <span style={{
                        marginLeft: '8px', fontSize: '9px', fontWeight: 700,
                        color: '#ef4444', background: 'rgba(239,68,68,0.15)',
                        padding: '1px 6px', borderRadius: '3px',
                      }}>
                        NEW FUND
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px', fontFamily: 'monospace' }}>
                    ISIN: {fund.isin} &nbsp;|&nbsp; Code: {fund.sbi_code}
                    {!fund.is_new_fund && (
                      <span> &nbsp;|&nbsp; Mapped: {fund.fund_code}</span>
                    )}
                  </div>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {fund.transactions.length} transaction{fund.transactions.length !== 1 ? 's' : ''}
                </div>
              </div>

              {/* Transaction table */}
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Date</th>
                    <th style={{ ...thStyle, textAlign: 'center' }}>Type</th>
                    <th style={thStyle}>Description</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Amount (₹)</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>NAV</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Units</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {fund.transactions.map((tx, ti) => {
                    const isDup = !!tx.isDuplicate;
                    const isBuy = tx.action === 'Buy';
                    return (
                      <tr key={ti} style={{
                        borderBottom: isDup ? dupRowBorder : '1px solid var(--border-light, rgba(255,255,255,0.05))',
                        background: isDup ? dupRowBg : undefined,
                        opacity: isDup ? 0.55 : 1,
                      }}>
                        <td style={{ ...tdStyle, fontSize: '11px', whiteSpace: 'nowrap' }}>
                          {formatDate(tx.date)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'center' }}>
                          <span style={{
                            display: 'inline-block',
                            fontSize: '9px', fontWeight: 700, letterSpacing: '0.5px',
                            padding: '2px 7px', borderRadius: '3px',
                            color: isBuy ? '#22c55e' : '#ef4444',
                            background: isBuy ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)',
                            border: `1px solid ${isBuy ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)'}`,
                          }}>
                            {isBuy ? 'BUY' : 'SELL'}
                          </span>
                          {isDup && (
                            <span style={{
                              display: 'inline-block', marginLeft: '4px',
                              fontSize: '9px', fontWeight: 700, color: '#d97706',
                              background: 'rgba(251,191,36,0.18)',
                              padding: '1px 5px', borderRadius: '3px',
                              letterSpacing: '0.5px',
                            }}>
                              DUP
                            </span>
                          )}
                        </td>
                        <td style={{
                          ...tdStyle,
                          maxWidth: '280px',
                          color: isDup ? 'var(--text-muted)' : 'var(--text-dim)',
                          textDecoration: isDup ? 'line-through' : 'none',
                        }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {tx.description}
                          </div>
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(tx.amount)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontSize: '11px' }}>
                          {tx.nav?.toFixed(4)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontSize: '11px' }}>
                          {tx.units?.toFixed(3)}
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-muted)' }}>
                          {tx.balance_units?.toFixed(3)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {importable.length} transaction{importable.length !== 1 ? 's' : ''} to import
            {dupCount > 0 && (
              <span style={{ marginLeft: '12px', color: '#d97706' }}>
                ({dupCount} duplicate{dupCount > 1 ? 's' : ''} will be skipped)
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={onCancel}
              disabled={confirming}
              style={{
                padding: '8px 20px', fontSize: '13px',
                background: 'var(--bg-input)', color: 'var(--text)',
                border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              disabled={confirming || importable.length === 0}
              style={{
                padding: '8px 20px', fontSize: '13px',
                background: (confirming || importable.length === 0) ? 'var(--bg-input)' : 'var(--green)',
                color: (confirming || importable.length === 0) ? 'var(--text-muted)' : '#fff',
                border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: (confirming || importable.length === 0) ? 'not-allowed' : 'pointer',
                fontWeight: 600,
              }}
            >
              {confirming
                ? 'Importing...'
                : importable.length === 0
                  ? 'All Duplicates \u2014 Nothing to Import'
                  : `Confirm Import (${importable.length} transaction${importable.length > 1 ? 's' : ''})`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
