import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddFDModal({ onAdd, onClose, initialData }) {
  const isEdit = !!(initialData?.id);
  const [form, setForm] = useState({
    bank: initialData?.bank || '',
    principal: initialData?.principal || '',
    interest_rate: initialData?.interest_rate || '',
    tenure_months: initialData?.tenure_months || '',
    start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
    maturity_date: initialData?.maturity_date || '',
    tds: initialData?.tds || '',
    status: initialData?.status || 'Active',
    remarks: initialData?.remarks || '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  // Auto-calculate maturity amount preview
  const maturityCalc = useMemo(() => {
    const p = parseFloat(form.principal) || 0;
    const r = parseFloat(form.interest_rate) || 0;
    const t = parseInt(form.tenure_months) || 0;
    if (p <= 0 || r <= 0 || t <= 0) return null;
    const n = 4; // quarterly compounding
    const years = t / 12;
    const maturity = p * Math.pow(1 + r / (100 * n), n * years);
    const interest = maturity - p;
    return { maturity: Math.round(maturity * 100) / 100, interest: Math.round(interest * 100) / 100 };
  }, [form.principal, form.interest_rate, form.tenure_months]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.bank || !form.principal || !form.interest_rate || !form.tenure_months || !form.start_date) return;
    setSubmitting(true);
    const payload = {
      ...form,
      principal: parseFloat(form.principal),
      interest_rate: parseFloat(form.interest_rate),
      tenure_months: parseInt(form.tenure_months),
      tds: parseFloat(form.tds) || 0,
    };
    if (isEdit) payload.id = initialData.id;
    await onAdd(payload);
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit Fixed Deposit' : 'Add Fixed Deposit'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Bank / Institution *</label>
            <input name="bank" value={form.bank} onChange={handleChange} placeholder="e.g. SBI, HDFC, Post Office" required autoFocus />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Principal Amount (₹) *</label>
              <input name="principal" type="number" step="0.01" min="1" value={form.principal} onChange={handleChange} placeholder="Deposit amount" required />
            </div>
            <div className="form-group">
              <label>Interest Rate (%) *</label>
              <input name="interest_rate" type="number" step="0.01" min="0.01" max="25" value={form.interest_rate} onChange={handleChange} placeholder="Annual rate" required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Tenure (months) *</label>
              <input name="tenure_months" type="number" min="1" max="120" value={form.tenure_months} onChange={handleChange} placeholder="e.g. 12, 24, 60" required />
            </div>
            <div className="form-group">
              <label>Start Date *</label>
              <input name="start_date" type="date" value={form.start_date} onChange={handleChange} required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Maturity Date</label>
              <input name="maturity_date" type="date" value={form.maturity_date} onChange={handleChange} placeholder="Auto-calculated if empty" />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Leave empty to auto-calculate</span>
            </div>
            <div className="form-group">
              <label>TDS (₹)</label>
              <input name="tds" type="number" step="0.01" min="0" value={form.tds} onChange={handleChange} placeholder="0" />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Status</label>
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="Active">Active</option>
                <option value="Matured">Matured</option>
                <option value="Premature">Premature Withdrawal</option>
                <option value="Closed">Closed</option>
              </select>
            </div>
            <div className="form-group">
              <label>Remarks</label>
              <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
            </div>
          </div>

          {/* Maturity Preview */}
          {maturityCalc && (
            <div style={{
              background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
              textAlign: 'center', marginTop: '8px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '32px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Maturity Amount</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text)' }}>{formatINR(maturityCalc.maturity)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Interest Earned</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--green)' }}>{formatINR(maturityCalc.interest)}</div>
                </div>
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEdit ? 'Update FD' : '+ Add FD'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
