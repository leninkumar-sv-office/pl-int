import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const COMPOUNDING_OPTIONS = [
  { value: 1,  label: 'Monthly' },
  { value: 4,  label: 'Quarterly' },
  { value: 6,  label: 'Half-Yearly' },
  { value: 12, label: 'Annually' },
];

export default function AddRDModal({ onAdd, onClose, initialData, mode }) {
  // mode: 'add' | 'edit' | 'installment'
  const isEdit = mode === 'edit';
  const isInstallment = mode === 'installment';

  const [form, setForm] = useState(isInstallment ? {
    date: new Date().toISOString().split('T')[0],
    amount: initialData?.monthly_amount || '',
    remarks: '',
  } : {
    bank: initialData?.bank || '',
    monthly_amount: initialData?.monthly_amount || '',
    interest_rate: initialData?.interest_rate || '',
    tenure_months: initialData?.tenure_months || '',
    compounding_frequency: initialData?.compounding_frequency || 4,
    start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
    maturity_date: initialData?.maturity_date || '',
    status: initialData?.status || 'Active',
    remarks: initialData?.remarks || '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  // Auto-calculate maturity preview using the actual compound interest formula
  const maturityCalc = useMemo(() => {
    if (isInstallment) return null;
    const sip = parseFloat(form.monthly_amount) || 0;
    const r = parseFloat(form.interest_rate) || 0;
    const t = parseInt(form.tenure_months) || 0;
    const freq = parseInt(form.compounding_frequency) || 4;
    if (sip <= 0 || r <= 0 || t <= 0) return null;

    const rateDec = r / 100;
    let cumulativeInterest = 0;
    for (let m = 1; m <= t; m++) {
      if (freq > 0 && m % freq === 0) {
        const interest = (sip * m + cumulativeInterest) * rateDec * freq / 12;
        cumulativeInterest += interest;
      }
    }
    const totalDeposited = sip * t;
    const maturity = Math.round((totalDeposited + cumulativeInterest) * 100) / 100;
    const interest = Math.round(cumulativeInterest * 100) / 100;
    return { maturity, totalDeposited, interest };
  }, [form.monthly_amount, form.interest_rate, form.tenure_months, form.compounding_frequency, isInstallment]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    if (isInstallment) {
      if (!form.date || !form.amount) { setSubmitting(false); return; }
      await onAdd({
        rd_id: initialData.id,
        date: form.date,
        amount: parseFloat(form.amount),
        remarks: form.remarks,
      });
    } else {
      if (!form.bank || !form.monthly_amount || !form.interest_rate || !form.tenure_months || !form.start_date) { setSubmitting(false); return; }
      const payload = {
        ...form,
        monthly_amount: parseFloat(form.monthly_amount),
        interest_rate: parseFloat(form.interest_rate),
        tenure_months: parseInt(form.tenure_months),
        compounding_frequency: parseInt(form.compounding_frequency),
      };
      if (isEdit) payload.id = initialData.id;
      await onAdd(payload);
    }
    setSubmitting(false);
  };

  if (isInstallment) {
    return (
      <div className="modal-overlay" onClick={onClose}>
        <div className="modal" onClick={(e) => e.stopPropagation()}>
          <h2>Add Installment</h2>
          <div style={{ fontSize: '13px', color: 'var(--text-dim)', marginBottom: '16px' }}>
            RD at {initialData?.bank} &mdash; {formatINR(initialData?.monthly_amount)}/month
          </div>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <div className="form-group">
                <label>Date *</label>
                <input name="date" type="date" value={form.date} onChange={handleChange} required />
              </div>
              <div className="form-group">
                <label>Amount ({'\u20B9'}) *</label>
                <input name="amount" type="number" step="0.01" min="1" value={form.amount} onChange={handleChange} required />
              </div>
            </div>
            <div className="form-group">
              <label>Remarks</label>
              <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional" />
            </div>
            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Adding...' : '+ Add Installment'}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  const selectedFreqLabel = COMPOUNDING_OPTIONS.find(o => o.value === parseInt(form.compounding_frequency))?.label || 'Quarterly';

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit Recurring Deposit' : 'Add Recurring Deposit'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Bank / Institution *</label>
            <input name="bank" value={form.bank} onChange={handleChange} placeholder="e.g. SBI, HDFC, Post Office" required autoFocus />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Monthly Amount ({'\u20B9'}) *</label>
              <input name="monthly_amount" type="number" step="0.01" min="1" value={form.monthly_amount} onChange={handleChange} placeholder="Monthly installment" required />
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
              <label>Compounding Frequency *</label>
              <select name="compounding_frequency" value={form.compounding_frequency} onChange={handleChange}>
                {COMPOUNDING_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Interest compounds {selectedFreqLabel.toLowerCase()}
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
              <label>Status</label>
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="Active">Active</option>
                <option value="Matured">Matured</option>
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
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                Projection: {formatINR(form.monthly_amount)}/month for {form.tenure_months} months at {form.interest_rate}% ({selectedFreqLabel} compounding)
              </div>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '32px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Total Deposits</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text)' }}>{formatINR(maturityCalc.totalDeposited)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Interest</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--green)' }}>{formatINR(maturityCalc.interest)}</div>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Maturity Amount</div>
                  <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--green)' }}>{formatINR(maturityCalc.maturity)}</div>
                </div>
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEdit ? 'Update RD' : '+ Add RD'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
