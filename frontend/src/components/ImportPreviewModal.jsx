import React, { useState, useCallback } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function ImportPreviewModal({ data, existingSymbols = new Set(), onConfirm, onCancel }) {
  const [confirming, setConfirming] = useState(false);
  // Editable symbol overrides: { index: newSymbol }
  const [symbolEdits, setSymbolEdits] = useState({});

  if (!data) return null;

  const { trade_date, contract_no, transactions, summary } = data;
  const isMultiPdf = !!data._multiPdf;
  const fileCount = data._fileCount || 1;

  // Apply symbol edits to transactions before filtering
  const editedTransactions = transactions.map((t, i) =>
    symbolEdits[i] !== undefined ? { ...t, symbol: symbolEdits[i] } : t
  );

  const buys = editedTransactions.filter(t => t.action === 'Buy');
  const sells = editedTransactions.filter(t => t.action === 'Sell');

  // Non-duplicate transactions (the ones that will actually be imported)
  const importableBuys = buys.filter(t => !t.isDuplicate);
  const importableSells = sells.filter(t => !t.isDuplicate);
  const importableCount = importableBuys.length + importableSells.length;

  const totalBuyCost = importableBuys.reduce((s, t) => s + t.net_total_after_levies, 0);
  const totalSellProceeds = importableSells.reduce((s, t) => s + t.net_total_after_levies, 0);

  const handleSymbolChange = useCallback((globalIdx, value) => {
    setSymbolEdits(prev => ({ ...prev, [globalIdx]: value.toUpperCase() }));
  }, []);

  const handleConfirm = async () => {
    if (importableCount === 0) return;
    setConfirming(true);
    try {
      // Only send non-duplicate transactions
      const toImport = editedTransactions.filter(t => !t.isDuplicate);
      await onConfirm(toImport);
    } finally {
      setConfirming(false);
    }
  };

  const isNewSymbol = (symbol) => !existingSymbols.has(symbol);

  const newRowBg = 'rgba(239,68,68,0.08)';
  const newRowBorder = '1px solid rgba(239,68,68,0.25)';
  const dupRowBg = 'rgba(251,191,36,0.10)';
  const dupRowBorder = '1px solid rgba(251,191,36,0.25)';

  // Shared row renderer for both BUY and SELL tables
  const renderRow = (t, i, filterAction) => {
    const globalIdx = transactions.indexOf(transactions.filter(x => x.action === filterAction)[i]);
    const isBuy = filterAction === 'Buy';
    const charges = isBuy
      ? t.net_total_after_levies - (t.wap * t.quantity)
      : (t.wap * t.quantity) - t.net_total_after_levies;
    const isNew = isNewSymbol(t.symbol);
    const isDup = !!t.isDuplicate;

    // Priority: duplicate > new symbol (dup takes visual precedence)
    const rowBg = isDup ? dupRowBg : isNew ? newRowBg : undefined;
    const rowBorder = isDup ? dupRowBorder : isNew ? newRowBorder : '1px solid var(--border-light, rgba(255,255,255,0.05))';

    return (
      <tr key={i} style={{
        borderBottom: rowBorder,
        background: rowBg,
        opacity: isDup ? 0.55 : 1,
      }}>
        <td style={{ ...tdStyle, fontSize: '11px', whiteSpace: 'nowrap' }}>{t.trade_date || trade_date}</td>
        <td style={tdStyle}>
          <input
            type="text"
            value={t.symbol}
            onChange={(e) => handleSymbolChange(globalIdx, e.target.value)}
            disabled={isDup}
            style={{
              background: isDup ? 'rgba(251,191,36,0.12)' : isNew ? 'rgba(239,68,68,0.12)' : 'var(--bg-input)',
              color: isDup ? 'var(--text-muted)' : 'var(--text)',
              border: isDup ? '1px solid rgba(251,191,36,0.4)' : isNew ? '1px solid rgba(239,68,68,0.4)' : '1px solid var(--border)',
              borderRadius: '3px',
              padding: '2px 6px', fontSize: '12px', fontWeight: 600,
              width: '140px',
              textDecoration: isDup ? 'line-through' : 'none',
            }}
          />
          {isDup && (
            <span style={{
              display: 'inline-block',
              marginLeft: '6px',
              fontSize: '9px',
              fontWeight: 700,
              color: '#d97706',
              background: 'rgba(251,191,36,0.18)',
              padding: '1px 5px',
              borderRadius: '3px',
              letterSpacing: '0.5px',
              verticalAlign: 'middle',
            }}>
              DUP
            </span>
          )}
          {isNew && !isDup && (
            <span style={{
              display: 'inline-block',
              marginLeft: '6px',
              fontSize: '9px',
              fontWeight: 700,
              color: '#ef4444',
              background: 'rgba(239,68,68,0.15)',
              padding: '1px 5px',
              borderRadius: '3px',
              letterSpacing: '0.5px',
              verticalAlign: 'middle',
            }}>
              NEW
            </span>
          )}
        </td>
        <td style={{ ...tdStyle, color: isDup ? 'var(--text-muted)' : 'var(--text-dim)', maxWidth: '180px' }}>
          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</div>
          <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{t.isin}</div>
          {isMultiPdf && t._sourceFile && (
            <div style={{ fontSize: '8px', color: 'var(--text-muted)', opacity: 0.7, marginTop: '1px' }}>
              {t._sourceFile.replace('.pdf', '').replace('.PDF', '')}
            </div>
          )}
        </td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{t.quantity}</td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.wap)}</td>
        <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(t.effective_price)}</td>
        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.net_total_after_levies)}</td>
        <td style={{ ...tdStyle, textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>{formatINR(charges)}</td>
      </tr>
    );
  };

  const newBuyCount = buys.filter(t => isNewSymbol(t.symbol) && !t.isDuplicate).length;
  const newSellCount = sells.filter(t => isNewSymbol(t.symbol) && !t.isDuplicate).length;
  const dupBuyCount = buys.filter(t => t.isDuplicate).length;
  const dupSellCount = sells.filter(t => t.isDuplicate).length;
  const totalDupCount = dupBuyCount + dupSellCount;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(0,0,0,0.6)', zIndex: 1000,
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      padding: '20px',
    }} onClick={onCancel}>
      <div style={{
        background: 'var(--bg-card)', borderRadius: 'var(--radius)',
        border: '1px solid var(--border)', maxWidth: '950px', width: '100%',
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
              Contract Note Preview
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
              {isMultiPdf ? `Trade Dates: ${trade_date}` : `Trade Date: ${trade_date}`}
              &nbsp;|&nbsp; CN# {contract_no || '\u2014'}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
              background: 'var(--green-bg)', color: 'var(--green)',
            }}>
              {summary.buys} Buys
            </span>
            <span style={{
              padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
              background: 'var(--red-bg)', color: 'var(--red)',
            }}>
              {summary.sells} Sells
            </span>
            {totalDupCount > 0 && (
              <span style={{
                padding: '3px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600,
                background: 'rgba(251,191,36,0.15)', color: '#d97706',
              }}>
                {totalDupCount} Duplicate{totalDupCount > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          {/* BUY table */}
          {buys.length > 0 && (
            <>
              <div style={{
                fontSize: '13px', fontWeight: 600, color: 'var(--green)',
                marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                BUY Transactions ({buys.length})
                {newBuyCount > 0 && (
                  <span style={{
                    fontSize: '10px', fontWeight: 600, color: '#ef4444',
                    background: 'rgba(239,68,68,0.12)', padding: '2px 7px',
                    borderRadius: '8px',
                  }}>
                    {newBuyCount} new symbol{newBuyCount > 1 ? 's' : ''}
                  </span>
                )}
                {dupBuyCount > 0 && (
                  <span style={{
                    fontSize: '10px', fontWeight: 600, color: '#d97706',
                    background: 'rgba(251,191,36,0.12)', padding: '2px 7px',
                    borderRadius: '8px',
                  }}>
                    {dupBuyCount} duplicate{dupBuyCount > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Trade Date</th>
                    <th style={{ ...thStyle, minWidth: '160px' }}>Symbol</th>
                    <th style={thStyle}>Name / ISIN</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Qty</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>WAP</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Effective Price</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Total Cost</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Charges</th>
                  </tr>
                </thead>
                <tbody>
                  {buys.map((t, i) => renderRow(t, i, 'Buy'))}
                  <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                    <td style={tdStyle} colSpan={3}>Total Buys (excl. duplicates)</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{importableBuys.reduce((s, t) => s + t.quantity, 0)}</td>
                    <td style={tdStyle}></td>
                    <td style={tdStyle}></td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(totalBuyCost)}</td>
                    <td style={tdStyle}></td>
                  </tr>
                </tbody>
              </table>
            </>
          )}

          {/* SELL table */}
          {sells.length > 0 && (
            <>
              <div style={{
                fontSize: '13px', fontWeight: 600, color: 'var(--red)',
                marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                SELL Transactions ({sells.length})
                {newSellCount > 0 && (
                  <span style={{
                    fontSize: '10px', fontWeight: 600, color: '#ef4444',
                    background: 'rgba(239,68,68,0.12)', padding: '2px 7px',
                    borderRadius: '8px',
                  }}>
                    {newSellCount} new symbol{newSellCount > 1 ? 's' : ''}
                  </span>
                )}
                {dupSellCount > 0 && (
                  <span style={{
                    fontSize: '10px', fontWeight: 600, color: '#d97706',
                    background: 'rgba(251,191,36,0.12)', padding: '2px 7px',
                    borderRadius: '8px',
                  }}>
                    {dupSellCount} duplicate{dupSellCount > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Trade Date</th>
                    <th style={{ ...thStyle, minWidth: '160px' }}>Symbol</th>
                    <th style={thStyle}>Name / ISIN</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Qty</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>WAP</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Effective Price</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Total Proceeds</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Charges</th>
                  </tr>
                </thead>
                <tbody>
                  {sells.map((t, i) => renderRow(t, i, 'Sell'))}
                  <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                    <td style={tdStyle} colSpan={3}>Total Sells (excl. duplicates)</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{importableSells.reduce((s, t) => s + t.quantity, 0)}</td>
                    <td style={tdStyle}></td>
                    <td style={tdStyle}></td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(totalSellProceeds)}</td>
                    <td style={tdStyle}></td>
                  </tr>
                </tbody>
              </table>
            </>
          )}
        </div>

        {/* Footer with actions */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Net Obligation: {formatINR(totalBuyCost - totalSellProceeds)}
            {totalDupCount > 0 && (
              <span style={{ marginLeft: '12px', color: '#d97706' }}>
                ({totalDupCount} duplicate{totalDupCount > 1 ? 's' : ''} will be skipped)
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
              disabled={confirming || importableCount === 0}
              style={{
                padding: '8px 20px', fontSize: '13px',
                background: (confirming || importableCount === 0) ? 'var(--bg-input)' : 'var(--green)',
                color: (confirming || importableCount === 0) ? 'var(--text-muted)' : '#fff',
                border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: (confirming || importableCount === 0) ? 'not-allowed' : 'pointer',
                fontWeight: 600,
              }}
            >
              {confirming
                ? 'Importing...'
                : importableCount === 0
                  ? 'All Duplicates \u2014 Nothing to Import'
                  : `Confirm Import (${importableCount} transaction${importableCount > 1 ? 's' : ''})`}
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
