import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function SellStockModal({ holding, onSell, onClose }) {
  const h = holding.holding;
  const live = holding.live;
  const currentPrice = live?.current_price || 0;

  const [quantity, setQuantity] = useState(h.quantity);
  const [sellPrice, setSellPrice] = useState(currentPrice || '');
  const [sellDate, setSellDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);

  const estimatedPL = useMemo(() => {
    const sp = parseFloat(sellPrice) || 0;
    const qty = parseInt(quantity) || 0;
    return (sp - h.buy_price) * qty;
  }, [sellPrice, quantity, h.buy_price]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!quantity || !sellPrice) return;
    setSubmitting(true);
    await onSell({
      holding_id: h.id,
      quantity: parseInt(quantity),
      sell_price: parseFloat(sellPrice),
      sell_date: sellDate,
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Sell {h.symbol}</h2>

        <div style={{ background: 'var(--bg-input)', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Holding</span>
            <span style={{ fontWeight: 600 }}>{h.symbol} <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>{h.exchange}</span></span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Shares Held</span>
            <span style={{ fontWeight: 600 }}>{h.quantity}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Buy Price</span>
            <span style={{ fontWeight: 600 }}>{formatINR(h.buy_price)}</span>
          </div>
          {currentPrice > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Current Price</span>
              <span style={{ fontWeight: 600, color: currentPrice >= h.buy_price ? 'var(--green)' : 'var(--red)' }}>
                {formatINR(currentPrice)}
              </span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Shares to Sell *</label>
              <input
                type="number"
                min="1"
                max={h.quantity}
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Sell Price (₹) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={sellPrice}
                onChange={(e) => setSellPrice(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>Sell Date</label>
            <input
              type="date"
              value={sellDate}
              onChange={(e) => setSellDate(e.target.value)}
            />
          </div>

          {/* Estimated P&L */}
          <div style={{
            background: estimatedPL >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
            borderRadius: '8px',
            padding: '16px',
            textAlign: 'center',
            marginTop: '8px',
          }}>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)', marginBottom: '4px' }}>Estimated P&L</div>
            <div style={{
              fontSize: '24px',
              fontWeight: 700,
              color: estimatedPL >= 0 ? 'var(--green)' : 'var(--red)',
            }}>
              {estimatedPL >= 0 ? '+' : ''}{formatINR(estimatedPL)}
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-danger" disabled={submitting}>
              {submitting ? 'Selling...' : `Sell ${quantity} Shares`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
