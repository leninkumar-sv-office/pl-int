import React, { useState, useCallback } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function DividendImportPreviewModal({ data, existingSymbols = new Set(), onConfirm, onCancel }) {
  const [confirming, setConfirming] = useState(false);
  const [symbolEdits, setSymbolEdits] = useState({});

  if (!data) return null;

  const { statement_period, dividends, summary } = data;
  const isMultiPdf = !!data._multiPdf;
  const fileCount = data._fileCount || 1;

  const editedDividends = dividends.map((d, i) =>
    symbolEdits[i] !== undefined ? { ...d, symbol: symbolEdits[i], symbol_matched: true } : d
  );

  const importable = editedDividends.filter(d => !d.isDuplicate);
  const dupCount = editedDividends.filter(d => d.isDuplicate).length;
  const unmatchedCount = editedDividends.filter(d => !d.symbol_matched && !d.isDuplicate).length;
  const importableAmount = importable.reduce((s, d) => s + d.amount, 0);

  const handleSymbolChange = useCallback((idx, value) => {
    setSymbolEdits(prev => ({ ...prev, [idx]: value.toUpperCase() }));
  }, []);

  // Build overrides map: raw company_raw → edited symbol (for persistence)
  const symbolOverrides = {};
  Object.entries(symbolEdits).forEach(([idx, newSymbol]) => {
    const original = dividends[parseInt(idx)];
    if (original && newSymbol && newSymbol !== original.symbol) {
      symbolOverrides[original.company_raw] = newSymbol;
    }
  });

  const handleConfirm = async () => {
    if (importable.length === 0) return;
    setConfirming(true);
    try {
      await onConfirm(importable, symbolOverrides);
    } finally {
      setConfirming(false);
    }
  };

  const unmatchedRowBg = 'rgba(239,68,68,0.08)';
  const unmatchedRowBorder = '1px solid rgba(239,68,68,0.25)';
  const dupRowBg = 'rgba(251,191,36,0.10)';
  const dupRowBorder = '1px solid rgba(251,191,36,0.25)';

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: '20px',
    }} onClick={onCancel}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', maxWidth: '900px', width: '100%',
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
              Dividend Import Preview
              {isMultiPdf && (
                <span style={{
                  marginLeft: '10px', fontSize: '11px', fontWeight: 600,
                  color: 'var(--blue)', background: 'rgba(59,130,246,0.12)',
                  padding: '2px 8px', borderRadius: '8px', verticalAlign: 'middle',
                }}>
                  {fileCount} PDFs
                </span>
              )}
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {statement_period ? `Period: ${statement_period}` : 'SBI Bank Statement'}
              &nbsp;|&nbsp; {summary.count} dividend{summary.count !== 1 ? 's' : ''} found
              &nbsp;|&nbsp; Total: {formatINR(summary.total_amount)}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
              background: 'var(--green-bg)', color: 'var(--green)',
            }}>
              {summary.matched} matched
            </span>
            {summary.unmatched > 0 && (
              <span style={{
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: 'var(--red-bg)', color: 'var(--red)',
              }}>
                {summary.unmatched} unmatched
              </span>
            )}
            {dupCount > 0 && (
              <span style={{
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: 'rgba(251,191,36,0.15)', color: '#d97706',
              }}>
                {dupCount} duplicate{dupCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={thStyle}>Date</th>
                <th style={{ ...thStyle, minWidth: '130px' }}>Symbol</th>
                <th style={thStyle}>Company (from PDF)</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Amount</th>
                <th style={{ ...thStyle, textAlign: 'center' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {editedDividends.map((d, i) => {
                const isDup = !!d.isDuplicate;
                const isUnmatched = !d.symbol_matched && !isDup;
                const isNew = d.symbol_matched && !existingSymbols.has(d.symbol) && !isDup;
                const rowBg = isDup ? dupRowBg : isUnmatched ? unmatchedRowBg : undefined;
                const rowBorder = isDup ? dupRowBorder : isUnmatched ? unmatchedRowBorder : '1px solid var(--border-light, rgba(255,255,255,0.05))';

                return (
                  <tr key={i} style={{
                    borderBottom: rowBorder,
                    background: rowBg,
                    opacity: isDup ? 0.55 : 1,
                  }}>
                    <td style={{ ...tdStyle, fontSize: '11px', whiteSpace: 'nowrap' }}>{d.date}</td>
                    <td style={tdStyle}>
                      <input
                        type="text"
                        value={d.symbol}
                        onChange={(e) => handleSymbolChange(i, e.target.value)}
                        disabled={isDup}
                        style={{
                          background: isDup ? 'rgba(251,191,36,0.12)' : isUnmatched ? 'rgba(239,68,68,0.12)' : 'var(--bg-input)',
                          color: isDup ? 'var(--text-muted)' : 'var(--text)',
                          border: isDup ? '1px solid rgba(251,191,36,0.4)' : isUnmatched ? '1px solid rgba(239,68,68,0.4)' : '1px solid var(--border)',
                          borderRadius: '3px',
                          padding: '2px 6px', fontSize: '12px', fontWeight: 600,
                          width: '120px',
                          textDecoration: isDup ? 'line-through' : 'none',
                        }}
                      />
                      {isDup && (
                        <span style={{
                          display: 'inline-block', marginLeft: '6px',
                          fontSize: '9px', fontWeight: 700, color: '#d97706',
                          background: 'rgba(251,191,36,0.18)', padding: '1px 5px',
                          borderRadius: '3px', letterSpacing: '0.5px', verticalAlign: 'middle',
                        }}>DUP</span>
                      )}
                      {isNew && (
                        <span style={{
                          display: 'inline-block', marginLeft: '6px',
                          fontSize: '9px', fontWeight: 700, color: '#ef4444',
                          background: 'rgba(239,68,68,0.15)', padding: '1px 5px',
                          borderRadius: '3px', letterSpacing: '0.5px', verticalAlign: 'middle',
                        }}>NEW</span>
                      )}
                    </td>
                    <td style={{ ...tdStyle, color: isDup ? 'var(--text-muted)' : 'var(--text-dim)', maxWidth: '250px' }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{d.company_raw}</div>
                      {d._sourceFile && (
                        <div style={{ fontSize: '8px', color: 'var(--text-muted)', opacity: 0.7, marginTop: '1px' }}>
                          {d._sourceFile.replace('.pdf', '').replace('.PDF', '')}
                        </div>
                      )}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, fontFamily: 'monospace' }}>
                      {formatINR(d.amount)}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      {isDup ? (
                        <span style={{
                          fontSize: '9px', fontWeight: 700, color: '#d97706',
                          background: 'rgba(251,191,36,0.18)', padding: '2px 7px',
                          borderRadius: '3px', letterSpacing: '0.5px',
                        }}>DUP</span>
                      ) : isUnmatched ? (
                        <span style={{
                          fontSize: '9px', fontWeight: 700, color: '#ef4444',
                          background: 'rgba(239,68,68,0.15)', padding: '2px 7px',
                          borderRadius: '3px', letterSpacing: '0.5px',
                        }}>EDIT SYMBOL</span>
                      ) : (
                        <span style={{
                          fontSize: '9px', fontWeight: 700, color: 'var(--green)',
                          background: 'var(--green-bg)', padding: '2px 7px',
                          borderRadius: '3px', letterSpacing: '0.5px',
                        }}>OK</span>
                      )}
                    </td>
                  </tr>
                );
              })}
              {/* Total row */}
              <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                <td style={tdStyle} colSpan={3}>Total (excl. duplicates)</td>
                <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace' }}>
                  {formatINR(importableAmount)}
                </td>
                <td style={{ ...tdStyle, textAlign: 'center', fontSize: '11px', color: 'var(--text-muted)' }}>
                  {importable.length} to import
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {importable.length} to import, {formatINR(importableAmount)}
            {dupCount > 0 && (
              <span style={{ marginLeft: '12px', color: '#d97706' }}>
                ({dupCount} duplicate{dupCount > 1 ? 's' : ''} skipped)
              </span>
            )}
            {unmatchedCount > 0 && (
              <span style={{ marginLeft: '12px', color: '#ef4444' }}>
                ({unmatchedCount} need symbol mapping)
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
                  : `Confirm Import (${importable.length} dividend${importable.length > 1 ? 's' : ''})`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

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
