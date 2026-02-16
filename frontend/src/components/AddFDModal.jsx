import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const PAYOUT_OPTIONS = [
  { value: 'Monthly',     period: 1,  label: 'Monthly' },
  { value: 'Quarterly',   period: 3,  label: 'Quarterly' },
  { value: 'Half-Yearly', period: 6,  label: 'Half-Yearly' },
  { value: 'Annually',    period: 12, label: 'Annually' },
];

export default function AddFDModal({ onAdd, onClose, initialData }) {
  const isEdit = !!(initialData?.id);
  const [form, setForm] = useState({
    bank: initialData?.bank || '',
    principal: initialData?.principal || '',
    interest_rate: initialData?.interest_rate || '',
    tenure_months: initialData?.tenure_months || '',
    type: initialData?.type || 'FD',
    interest_payout: initialData?.interest_payout || 'Quarterly',
    start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
    maturity_date: initialData?.maturity_date || '',
    tds: initialData?.tds || '',
    status: initialData?.status || 'Active',
    remarks: initialData?.remarks || '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => {
      const next = { ...prev, [name]: value };
      // MIS always pays monthly
      if (name === 'type' && value === 'MIS') {
        next.interest_payout = 'Monthly';
      }
      return next;
    });
  };

  // Auto-calculate maturity amount preview using payout frequency
  const maturityCalc = useMemo(() => {
    const p = parseFloat(form.principal) || 0;
    const r = parseFloat(form.interest_rate) || 0;
    const t = parseInt(form.tenure_months) || 0;
    if (p <= 0 || r <= 0 || t <= 0) return null;

    const opt = PAYOUT_OPTIONS.find(o => o.value === form.interest_payout) || PAYOUT_OPTIONS[1];
    const periodMonths = opt.period;
    const periodsPerYear = 12 / periodMonths;
    const numPeriods = Math.floor(t / periodMonths);
    const interestPerPeriod = p * (r / 100) / periodsPerYear;
    const totalInterest = Math.round(interestPerPeriod * numPeriods * 100) / 100;
    const maturity = Math.round((p + totalInterest) * 100) / 100;
    return { maturity, interest: totalInterest };
  }, [form.principal, form.interest_rate, form.tenure_months, form.interest_payout]);

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

  const payoutLabel = PAYOUT_OPTIONS.find(o => o.value === form.interest_payout)?.label || 'Quarterly';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit Fixed Deposit' : 'Add Fixed Deposit'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Bank / Institution *</label>
              <input name="bank" value={form.bank} onChange={handleChange} placeholder="e.g. SBI, HDFC, Post Office" required autoFocus />
            </div>
            <div className="form-group">
              <label>Type *</label>
              <select name="type" value={form.type} onChange={handleChange}>
                <option value="FD">Fixed Deposit (FD)</option>
                <option value="MIS">Monthly Income Scheme (MIS)</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Principal Amount ({'\u20B9'}) *</label>
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
              <label>Interest Payout *</label>
              <select name="interest_payout" value={form.interest_payout} onChange={handleChange} disabled={form.type === 'MIS'}>
                {PAYOUT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {form.type === 'MIS' ? 'MIS always pays monthly' : `Interest paid ${payoutLabel.toLowerCase()}`}
              </span>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Start Date *</label>
              <input name="start_date" type="date" value={form.start_date} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label>Maturity Date</label>
              <input name="maturity_date" type="date" value={form.maturity_date} onChange={handleChange} />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Leave empty to auto-calculate</span>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>TDS ({'\u20B9'})</label>
              <input name="tds" type="number" step="0.01" min="0" value={form.tds} onChange={handleChange} placeholder="0" />
            </div>
            <div className="form-group">
              <label>Status</label>
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="Active">Active</option>
                <option value="Matured">Matured</option>
                <option value="Premature">Premature Withdrawal</option>
                <option value="Closed">Closed</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Remarks</label>
            <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
          </div>

          {/* Maturity Preview */}
          {maturityCalc && (
            <div style={{
              background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
              textAlign: 'center', marginTop: '8px',
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                Projection: {formatINR(form.principal)} at {form.interest_rate}% for {form.tenure_months} months ({payoutLabel} payout)
              </div>
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
