import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

/**
 * BulkSellModal — sell selected held lots at once.
 *
 * Props:
 *   items: [{ holding, live }]   ← flat array of lot-level portfolio items
 *   onSell: async ({ holding_id, quantity, sell_price, sell_date }) => ...
 *   onClose: () => void
 */
export default function BulkSellModal({ items, onSell, onClose }) {
  const [sellDate, setSellDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);
  const [progress, setProgress] = useState({ done: 0, total: 0 });

  // Group items by symbol for display and per-stock sell price editing
  const grouped = useMemo(() => {
    const map = {};
    for (const item of items) {
      const sym = item.holding.symbol;
      if (!map[sym]) {
        map[sym] = {
          symbol: sym,
          exchange: item.holding.exchange,
          name: item.holding.name || sym,
          lots: [],
          live: item.live,
        };
      }
      map[sym].lots.push(item);
    }
    return Object.values(map);
  }, [items]);

  // Editable sell price per stock (default to current live price)
  const [priceOverrides, setPriceOverrides] = useState(() => {
    const map = {};
    for (const group of grouped) {
      const cp = group.live?.current_price || 0;
      map[group.symbol] = cp > 0 ? cp.toString() : '';
    }
    return map;
  });

  const updatePrice = (symbol, val) => {
    setPriceOverrides(prev => ({ ...prev, [symbol]: val }));
  };

  // Compute summary
  const summary = useMemo(() => {
    let totalLots = 0;
    let totalQty = 0;
    let totalInvested = 0;
    let totalSellValue = 0;
    const rows = [];

    for (const group of grouped) {
      const sp = parseFloat(priceOverrides[group.symbol]) || 0;
      let stockQty = 0;
      let stockInvested = 0;
      let stockSellValue = 0;
      let lotCount = 0;

      for (const item of group.lots) {
        const h = item.holding;
        if (h.quantity <= 0) continue;
        stockQty += h.quantity;
        stockInvested += h.buy_price * h.quantity;
        stockSellValue += sp * h.quantity;
        lotCount++;
      }

      totalLots += lotCount;
      totalQty += stockQty;
      totalInvested += stockInvested;
      totalSellValue += stockSellValue;

      rows.push({
        symbol: group.symbol,
        exchange: group.exchange,
        name: group.name,
        qty: stockQty,
        numLots: lotCount,
        avgBuy: stockQty > 0 ? stockInvested / stockQty : 0,
        sellPrice: sp,
        invested: stockInvested,
        sellValue: stockSellValue,
        pl: stockSellValue - stockInvested,
      });
    }

    return {
      rows,
      totalLots,
      totalQty,
      totalInvested,
      totalSellValue,
      totalPL: totalSellValue - totalInvested,
    };
  }, [grouped, priceOverrides]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    // Build flat list of all sell operations
    const ops = [];
    for (const group of grouped) {
      const sp = parseFloat(priceOverrides[group.symbol]) || 0;
      if (sp <= 0) continue;
      for (const item of group.lots) {
        const h = item.holding;
        if (h.quantity <= 0) continue;
        ops.push({
          holding_id: h.id,
          quantity: h.quantity,
          sell_price: sp,
          sell_date: sellDate,
        });
      }
    }

    setProgress({ done: 0, total: ops.length });

    // Execute sequentially to avoid race conditions
    let done = 0;
    for (const op of ops) {
      try {
        await onSell(op);
      } catch {
        // Continue on error — individual failures handled by parent
      }
      done++;
      setProgress({ done, total: ops.length });
    }

    setSubmitting(false);
    onClose();
  };

  const allPricesValid = grouped.every((group) => {
    const sp = parseFloat(priceOverrides[group.symbol]);
    return sp > 0;
  });

  const stockCount = grouped.length;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '720px', width: '95%' }}>
        <h2>Bulk Sell — {summary.totalLots} Lot{summary.totalLots !== 1 ? 's' : ''} across {stockCount} Stock{stockCount !== 1 ? 's' : ''}</h2>

        <form onSubmit={handleSubmit}>
          {/* Per-stock summary table */}
          <div style={{
            maxHeight: '320px',
            overflowY: 'auto',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            marginBottom: '16px',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)', position: 'sticky', top: 0, zIndex: 1 }}>
                  <th style={thStyle}>Stock</th>
                  <th style={thStyle}>Qty</th>
                  <th style={thStyle}>Lots</th>
                  <th style={thStyle}>Avg Buy</th>
                  <th style={{ ...thStyle, minWidth: '100px' }}>Sell Price</th>
                  <th style={thStyle}>Est. P&L</th>
                </tr>
              </thead>
              <tbody>
                {summary.rows.map((row) => (
                  <tr key={row.symbol} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 600 }}>{row.symbol}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{row.exchange}</div>
                    </td>
                    <td style={{ ...tdStyle, fontWeight: 600 }}>{row.qty}</td>
                    <td style={tdStyle}>{row.numLots}</td>
                    <td style={tdStyle}>{formatINR(row.avgBuy)}</td>
                    <td style={tdStyle}>
                      <input
                        type="number"
                        step="0.01"
                        min="0.01"
                        value={priceOverrides[row.symbol]}
                        onChange={(e) => updatePrice(row.symbol, e.target.value)}
                        style={{
                          width: '100%',
                          padding: '4px 8px',
                          background: 'var(--bg-input)',
                          border: '1px solid var(--border)',
                          borderRadius: '4px',
                          color: 'var(--text)',
                          fontSize: '13px',
                        }}
                      />
                    </td>
                    <td style={{
                      ...tdStyle,
                      fontWeight: 600,
                      color: row.pl >= 0 ? 'var(--green)' : 'var(--red)',
                    }}>
                      {row.sellPrice > 0
                        ? `${row.pl >= 0 ? '+' : ''}${formatINR(row.pl)}`
                        : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Sell date */}
          <div className="form-row" style={{ marginBottom: '12px' }}>
            <div className="form-group">
              <label>Sell Date *</label>
              <input
                type="date"
                value={sellDate}
                onChange={(e) => setSellDate(e.target.value)}
                required
              />
            </div>
            <div className="form-group" />
          </div>

          {/* Summary card */}
          <div style={{
            background: summary.totalPL >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '16px',
            display: 'flex',
            justifyContent: 'space-around',
            flexWrap: 'wrap',
            gap: '12px',
          }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '2px' }}>Stocks</div>
              <div style={{ fontWeight: 700, fontSize: '18px' }}>{stockCount}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '2px' }}>Total Lots</div>
              <div style={{ fontWeight: 700, fontSize: '18px' }}>{summary.totalLots}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '2px' }}>Total Qty</div>
              <div style={{ fontWeight: 700, fontSize: '18px' }}>{summary.totalQty}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '2px' }}>Total Invested</div>
              <div style={{ fontWeight: 700, fontSize: '16px' }}>{formatINR(summary.totalInvested)}</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '2px' }}>Estimated P&L</div>
              <div style={{
                fontWeight: 700,
                fontSize: '20px',
                color: summary.totalPL >= 0 ? 'var(--green)' : 'var(--red)',
              }}>
                {summary.totalPL >= 0 ? '+' : ''}{formatINR(summary.totalPL)}
              </div>
            </div>
          </div>

          {/* Progress bar during submission */}
          {submitting && progress.total > 0 && (
            <div style={{ marginBottom: '12px' }}>
              <div style={{
                background: 'var(--bg-input)',
                borderRadius: '4px',
                height: '8px',
                overflow: 'hidden',
              }}>
                <div style={{
                  background: 'var(--blue)',
                  height: '100%',
                  width: `${(progress.done / progress.total) * 100}%`,
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px', textAlign: 'center' }}>
                Selling {progress.done} of {progress.total} lots...
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-danger"
              disabled={submitting || !allPricesValid}
              style={{ fontWeight: 600 }}
            >
              {submitting
                ? `Selling ${progress.done}/${progress.total}...`
                : `Sell All ${summary.totalQty} Shares`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const thStyle = {
  padding: '8px 12px',
  textAlign: 'left',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: 'var(--text-dim)',
  fontWeight: 600,
  borderBottom: '1px solid var(--border)',
  background: 'var(--bg-card)',
};

const tdStyle = {
  padding: '8px 12px',
  fontSize: '13px',
  verticalAlign: 'middle',
};
