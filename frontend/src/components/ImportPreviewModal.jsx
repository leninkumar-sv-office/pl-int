import React, { useState, useCallback } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function ImportPreviewModal({ data, onConfirm, onCancel }) {
  const [confirming, setConfirming] = useState(false);
  // Editable symbol overrides: { index: newSymbol }
  const [symbolEdits, setSymbolEdits] = useState({});

  if (!data) return null;

  const { trade_date, contract_no, transactions, summary } = data;

  // Apply symbol edits to transactions before filtering
  const editedTransactions = transactions.map((t, i) =>
    symbolEdits[i] !== undefined ? { ...t, symbol: symbolEdits[i] } : t
  );

  const buys = editedTransactions.filter(t => t.action === 'Buy');
  const sells = editedTransactions.filter(t => t.action === 'Sell');

  const totalBuyCost = buys.reduce((s, t) => s + t.net_total_after_levies, 0);
  const totalSellProceeds = sells.reduce((s, t) => s + t.net_total_after_levies, 0);

  const handleSymbolChange = useCallback((globalIdx, value) => {
    setSymbolEdits(prev => ({ ...prev, [globalIdx]: value.toUpperCase() }));
  }, []);

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await onConfirm(editedTransactions);
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
              Contract Note Preview
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Trade Date: {trade_date} &nbsp;|&nbsp; CN# {contract_no || '—'}
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
          </div>
        </div>

        {/* Scrollable body */}
        <div style={{ flex: 1, overflow: 'auto', padding: '16px 20px' }}>
          {/* BUY table */}
          {buys.length > 0 && (
            <>
              <div style={{
                fontSize: '13px', fontWeight: 600, color: 'var(--green)',
                marginBottom: '8px',
              }}>
                BUY Transactions ({buys.length})
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Symbol</th>
                    <th style={thStyle}>Name / ISIN</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Qty</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>WAP</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Effective Price</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Total Cost</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Charges</th>
                  </tr>
                </thead>
                <tbody>
                  {buys.map((t, i) => {
                    const globalIdx = transactions.indexOf(transactions.filter(x => x.action === 'Buy')[i]);
                    const charges = t.net_total_after_levies - (t.wap * t.quantity);
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-light, rgba(255,255,255,0.05))' }}>
                        <td style={tdStyle}>
                          <input
                            type="text"
                            value={t.symbol}
                            onChange={(e) => handleSymbolChange(globalIdx, e.target.value)}
                            style={{
                              background: 'var(--bg-input)', color: 'var(--text)',
                              border: '1px solid var(--border)', borderRadius: '3px',
                              padding: '2px 6px', fontSize: '12px', fontWeight: 600,
                              width: '100px',
                            }}
                          />
                        </td>
                        <td style={{ ...tdStyle, color: 'var(--text-dim)', maxWidth: '180px' }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</div>
                          <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{t.isin}</div>
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{t.quantity}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.wap)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(t.effective_price)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.net_total_after_levies)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>{formatINR(charges)}</td>
                      </tr>
                    );
                  })}
                  <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                    <td style={tdStyle} colSpan={2}>Total Buys</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{buys.reduce((s, t) => s + t.quantity, 0)}</td>
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
                marginBottom: '8px',
              }}>
                SELL Transactions ({sells.length})
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <th style={thStyle}>Symbol</th>
                    <th style={thStyle}>Name / ISIN</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Qty</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>WAP</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Effective Price</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Total Proceeds</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Charges</th>
                  </tr>
                </thead>
                <tbody>
                  {sells.map((t, i) => {
                    const globalIdx = transactions.indexOf(transactions.filter(x => x.action === 'Sell')[i]);
                    const charges = (t.wap * t.quantity) - t.net_total_after_levies;
                    return (
                      <tr key={i} style={{ borderBottom: '1px solid var(--border-light, rgba(255,255,255,0.05))' }}>
                        <td style={tdStyle}>
                          <input
                            type="text"
                            value={t.symbol}
                            onChange={(e) => handleSymbolChange(globalIdx, e.target.value)}
                            style={{
                              background: 'var(--bg-input)', color: 'var(--text)',
                              border: '1px solid var(--border)', borderRadius: '3px',
                              padding: '2px 6px', fontSize: '12px', fontWeight: 600,
                              width: '100px',
                            }}
                          />
                        </td>
                        <td style={{ ...tdStyle, color: 'var(--text-dim)', maxWidth: '180px' }}>
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.name}</div>
                          <div style={{ fontSize: '9px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{t.isin}</div>
                        </td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{t.quantity}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.wap)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(t.effective_price)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(t.net_total_after_levies)}</td>
                        <td style={{ ...tdStyle, textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>{formatINR(charges)}</td>
                      </tr>
                    );
                  })}
                  <tr style={{ borderTop: '2px solid var(--border)', fontWeight: 700 }}>
                    <td style={tdStyle} colSpan={2}>Total Sells</td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>{sells.reduce((s, t) => s + t.quantity, 0)}</td>
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
              disabled={confirming}
              style={{
                padding: '8px 20px', fontSize: '13px',
                background: confirming ? 'var(--bg-input)' : 'var(--green)',
                color: confirming ? 'var(--text-muted)' : '#fff',
                border: 'none', borderRadius: 'var(--radius-sm)',
                cursor: confirming ? 'wait' : 'pointer',
                fontWeight: 600,
              }}
            >
              {confirming ? 'Importing...' : `Confirm Import (${summary.total} transactions)`}
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
