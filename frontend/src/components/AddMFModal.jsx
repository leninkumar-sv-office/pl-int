import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddMFModal({ onAdd, onClose, initialData, funds }) {
  const [form, setForm] = useState({
    fund_code: initialData?.fund_code || '',
    fund_name: initialData?.name || initialData?.fund_name || '',
    units: '',
    nav: '',
    buy_date: new Date().toISOString().split('T')[0],
    remarks: '',
  });
  const [submitting, setSubmitting] = useState(false);

  // Pre-filled from an existing fund row (read-only name)
  const isExistingFund = !!(initialData?.fund_code);

  const totalAmount = useMemo(() => {
    const u = parseFloat(form.units) || 0;
    const n = parseFloat(form.nav) || 0;
    return u * n;
  }, [form.units, form.nav]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleFundSelect = (e) => {
    const code = e.target.value;
    const found = funds?.find(f => f.fund_code === code);
    if (found) {
      setForm(prev => ({
        ...prev,
        fund_code: found.fund_code,
        fund_name: found.name,
        nav: found.current_nav > 0 ? String(found.current_nav) : '',
      }));
    } else {
      setForm(prev => ({ ...prev, fund_code: code, fund_name: '' }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.fund_name || !form.units || !form.nav || !form.buy_date) return;
    setSubmitting(true);
    await onAdd({
      ...form,
      units: parseFloat(form.units),
      nav: parseFloat(form.nav),
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Buy Mutual Fund</h2>
        <form onSubmit={handleSubmit}>

          {isExistingFund ? (
            <div className="form-group">
              <label>Fund Name</label>
              <input
                value={form.fund_name}
                disabled
                style={{ borderColor: 'var(--green)', opacity: 0.85 }}
              />
            </div>
          ) : (
            <>
              {funds && funds.length > 0 && (
                <div className="form-group">
                  <label>Select Existing Fund</label>
                  <select
                    value={form.fund_code}
                    onChange={handleFundSelect}
                    style={{ marginBottom: '8px' }}
                  >
                    <option value="">-- New Fund --</option>
                    {funds.map(f => (
                      <option key={f.fund_code} value={f.fund_code}>
                        {f.name.replace(/ - Direct Plan.*| - Direct Growth.*| Direct Growth.*/i, '')}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-group">
                <label>Fund Name *</label>
                <input
                  name="fund_name"
                  value={form.fund_name}
                  onChange={handleChange}
                  placeholder="e.g. SBI Small Cap Fund - Direct Growth"
                  required
                  autoFocus={!isExistingFund}
                />
              </div>
              <div className="form-group">
                <label>Fund Code</label>
                <input
                  name="fund_code"
                  value={form.fund_code}
                  onChange={handleChange}
                  placeholder="e.g. MUTF_IN:SBI_SMAL_CAP_..."
                  style={{ fontSize: '12px', color: 'var(--text-muted)' }}
                />
              </div>
            </>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>Units *</label>
              <input
                name="units"
                type="number"
                step="any"
                min="0.001"
                value={form.units}
                onChange={handleChange}
                placeholder="Number of units"
                required
              />
            </div>
            <div className="form-group">
              <label>NAV (₹) *</label>
              <input
                name="nav"
                type="number"
                step="any"
                min="0.01"
                value={form.nav}
                onChange={handleChange}
                placeholder="NAV per unit"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Buy Date *</label>
              <input
                name="buy_date"
                type="date"
                value={form.buy_date}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Remarks</label>
              <input
                name="remarks"
                value={form.remarks}
                onChange={handleChange}
                placeholder="Optional notes"
              />
            </div>
          </div>

          {/* Total Amount */}
          {totalAmount > 0 && (
            <div style={{
              background: 'var(--bg-input)',
              borderRadius: '8px',
              padding: '12px 16px',
              textAlign: 'center',
              marginTop: '8px',
            }}>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Total Investment</div>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
                {formatINR(totalAmount)}
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Adding...' : '+ Buy MF'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
