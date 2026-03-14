import React, { useState } from 'react';

const TIER_OPTIONS = ['Tier I', 'Tier II'];
const FUND_MANAGERS = [
  'SBI Pension Funds',
  'LIC Pension Fund',
  'UTI Retirement Solutions',
  'HDFC Pension Management',
  'ICICI Prudential Pension Fund',
  'Kotak Mahindra Pension Fund',
  'Aditya Birla Sun Life Pension',
  'Tata Pension Management',
  'Max Life Pension Fund',
  'Axis Pension Fund',
];
const SCHEME_OPTIONS = ['Auto Choice', 'Active Choice', 'Aggressive (LC75)', 'Moderate (LC50)', 'Conservative (LC25)'];
const STATUS_OPTIONS = ['Active', 'Frozen', 'Closed'];

export default function AddNPSModal({ onSubmit, onClose, initialData, mode = 'add' }) {
  // mode: 'add' | 'edit' | 'contribution'
  const isEdit = mode === 'edit';
  const isContribution = mode === 'contribution';

  const [form, setForm] = useState(() => {
    if (isContribution) {
      return {
        date: new Date().toISOString().split('T')[0],
        amount: '',
        remarks: '',
      };
    }
    return {
      account_name: initialData?.account_name || 'NPS Account',
      pran: initialData?.pran || '',
      tier: initialData?.tier || 'Tier I',
      fund_manager: initialData?.fund_manager || '',
      scheme_preference: initialData?.scheme_preference || 'Auto Choice',
      start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
      current_value: initialData?.current_value || 0,
      status: initialData?.status || 'Active',
      remarks: initialData?.remarks || '',
    };
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    if (isContribution) {
      if (!form.date || !form.amount) { setSubmitting(false); return; }
      await onSubmit({
        nps_id: initialData.id,
        date: form.date,
        amount: parseFloat(form.amount),
        remarks: form.remarks,
      });
    } else {
      if (!form.account_name || !form.start_date) { setSubmitting(false); return; }
      const payload = {
        ...form,
        current_value: parseFloat(form.current_value) || 0,
      };
      if (isEdit) payload.id = initialData.id;
      await onSubmit(payload);
    }
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>
          {isContribution ? `Add Contribution — ${initialData.account_name}` : isEdit ? 'Edit NPS Account' : 'Add NPS Account'}
        </h2>
        <form onSubmit={handleSubmit}>
          {isContribution ? (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Date *</label>
                  <input name="date" type="date" value={form.date} onChange={handleChange} required autoFocus />
                </div>
                <div className="form-group">
                  <label>Amount ({'\u20B9'}) *</label>
                  <input name="amount" type="number" step="1" min="1" value={form.amount} onChange={handleChange} placeholder="Contribution amount" required />
                </div>
              </div>
              <div className="form-group">
                <label>Remarks</label>
                <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '8px 0' }}>
                NPS has no per-year cap. Contributions qualify for tax deduction under Sec 80CCD(1) up to 10% of salary
                (within 80C limit of {'\u20B9'}1.5L) + additional {'\u20B9'}50,000 under 80CCD(1B).
              </div>
            </>
          ) : (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Account Name *</label>
                  <input name="account_name" value={form.account_name} onChange={handleChange} placeholder="e.g. NPS - Self" required autoFocus />
                </div>
                <div className="form-group">
                  <label>PRAN</label>
                  <input name="pran" value={form.pran} onChange={handleChange} placeholder="12-digit PRAN number" />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Tier *</label>
                  <select name="tier" value={form.tier} onChange={handleChange}>
                    {TIER_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Fund Manager</label>
                  <select name="fund_manager" value={form.fund_manager} onChange={handleChange}>
                    <option value="">-- Select --</option>
                    {FUND_MANAGERS.map(fm => <option key={fm} value={fm}>{fm}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Scheme Preference</label>
                  <select name="scheme_preference" value={form.scheme_preference} onChange={handleChange}>
                    {SCHEME_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label>Start Date *</label>
                  <input name="start_date" type="date" value={form.start_date} onChange={handleChange} required />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Current Value ({'\u20B9'})</label>
                  <input name="current_value" type="number" step="0.01" min="0" value={form.current_value} onChange={handleChange} placeholder="Current corpus value" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Update manually — NPS NAV not auto-fetched</span>
                </div>
                <div className="form-group">
                  <label>Status</label>
                  <select name="status" value={form.status} onChange={handleChange}>
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Remarks</label>
                <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
              </div>

              {/* NPS Tax Info Box */}
              <div style={{
                background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
                marginTop: '8px',
              }}>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
                  <strong style={{ color: 'var(--text-dim)' }}>NPS Tax Benefits (80CCD):</strong><br />
                  {'\u2022'} 80CCD(1): Employee contribution up to 10% of salary (within {'\u20B9'}1.5L 80C limit)<br />
                  {'\u2022'} 80CCD(1B): Additional {'\u20B9'}50,000 deduction (over and above 80C)<br />
                  {'\u2022'} 80CCD(2): Employer contribution up to 10% of salary (no cap)<br />
                  {'\u2022'} 60% corpus tax-free at withdrawal; 40% must buy annuity
                </div>
              </div>
            </>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isContribution ? '+ Add Contribution' : isEdit ? 'Update NPS' : '+ Add NPS'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
