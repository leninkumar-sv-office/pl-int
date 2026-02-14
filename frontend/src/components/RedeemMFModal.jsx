import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function RedeemMFModal({ fund, onRedeem, onClose }) {
  const currentNav = fund.current_nav || 0;
  const totalHeldUnits = fund.total_held_units || 0;
  const avgNav = fund.avg_nav || 0;
  const fundName = (fund.name || '').replace(/ - Direct Plan.*| - Direct Growth.*| Direct Growth.*/i, '');

  const [units, setUnits] = useState(totalHeldUnits);
  const [redeemNav, setRedeemNav] = useState(currentNav || '');
  const [sellDate, setSellDate] = useState(new Date().toISOString().split('T')[0]);
  const [submitting, setSubmitting] = useState(false);

  const estimatedAmount = useMemo(() => {
    const u = parseFloat(units) || 0;
    const n = parseFloat(redeemNav) || 0;
    return u * n;
  }, [units, redeemNav]);

  const estimatedPL = useMemo(() => {
    const u = parseFloat(units) || 0;
    const n = parseFloat(redeemNav) || 0;
    return (n - avgNav) * u;
  }, [units, redeemNav, avgNav]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!units || !redeemNav) return;
    setSubmitting(true);
    await onRedeem({
      fund_code: fund.fund_code,
      units: parseFloat(units),
      nav: parseFloat(redeemNav),
      sell_date: sellDate,
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Redeem {fundName}</h2>

        {/* Fund Info */}
        <div style={{ background: 'var(--bg-input)', borderRadius: '8px', padding: '16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Fund</span>
            <span style={{ fontWeight: 600, fontSize: '13px' }}>{fundName}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Units Held</span>
            <span style={{ fontWeight: 600 }}>{totalHeldUnits.toLocaleString('en-IN', { minimumFractionDigits: 3 })}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <span style={{ color: 'var(--text-dim)' }}>Avg NAV</span>
            <span style={{ fontWeight: 600 }}>{formatINR(avgNav)}</span>
          </div>
          {currentNav > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-dim)' }}>Current NAV</span>
              <span style={{ fontWeight: 600, color: currentNav >= avgNav ? 'var(--green)' : 'var(--red)' }}>
                {formatINR(currentNav)}
              </span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Units to Redeem *</label>
              <input
                type="number"
                step="0.001"
                min="0.001"
                max={totalHeldUnits}
                value={units}
                onChange={(e) => setUnits(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Redemption NAV (₹) *</label>
              <input
                type="number"
                step="0.01"
                min="0.01"
                value={redeemNav}
                onChange={(e) => setRedeemNav(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Redemption Date *</label>
              <input
                type="date"
                value={sellDate}
                onChange={(e) => setSellDate(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>Estimated Amount</label>
              <div style={{ padding: '8px 0', fontSize: '16px', fontWeight: 600, color: 'var(--text)' }}>
                {formatINR(estimatedAmount)}
              </div>
            </div>
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
              {submitting ? 'Redeeming...' : `Redeem ${parseFloat(units || 0).toFixed(3)} Units`}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
