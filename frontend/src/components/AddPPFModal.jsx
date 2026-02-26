import React, { useState, useMemo } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddPPFModal({ onSubmit, onClose, initialData, mode = 'add' }) {
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
      account_name: initialData?.account_name || 'PPF Account',
      bank: initialData?.bank || 'Post Office',
      account_number: initialData?.account_number || '',
      interest_rate: initialData?.interest_rate || 7.1,
      start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
      tenure_years: initialData?.tenure_years || 15,
      payment_type: initialData?.payment_type || (
        // Detect from existing data: if sip_end_date === start_date, it was one-time
        (initialData?.sip_amount > 0 && initialData?.sip_end_date && initialData?.sip_end_date === initialData?.start_date)
          ? 'one_time' : (initialData?.sip_amount > 0 ? 'sip' : 'one_time')
      ),
      amount_added: initialData?.amount_added || (
        // For one-time, pre-fill from sip_amount if sip_end_date === start_date
        (initialData?.sip_amount > 0 && initialData?.sip_end_date === initialData?.start_date) ? initialData.sip_amount : ''
      ),
      sip_amount: initialData?.sip_amount || '',
      sip_frequency: initialData?.sip_frequency || 'monthly',
      sip_end_date: (initialData?.sip_end_date === initialData?.start_date) ? '' : (initialData?.sip_end_date || ''),
      remarks: initialData?.remarks || '',
    };
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  // Maturity preview for add/edit
  const maturityCalc = useMemo(() => {
    if (isContribution) return null;
    const r = parseFloat(form.interest_rate) || 0;
    const t = parseInt(form.tenure_years) || 15;
    if (r <= 0) return null;
    // Assuming max yearly deposit of 1.5L for projection
    const yearlyDeposit = 150000;
    let balance = 0;
    for (let i = 0; i < t; i++) {
      balance = (balance + yearlyDeposit) * (1 + r / 100);
    }
    const totalDeposited = yearlyDeposit * t;
    return {
      projected_balance: Math.round(balance * 100) / 100,
      total_deposited: totalDeposited,
      total_interest: Math.round((balance - totalDeposited) * 100) / 100,
    };
  }, [form.interest_rate, form.tenure_years, isContribution]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);

    if (isContribution) {
      if (!form.date || !form.amount) { setSubmitting(false); return; }
      await onSubmit({
        ppf_id: initialData.id,
        date: form.date,
        amount: parseFloat(form.amount),
        remarks: form.remarks,
      });
    } else {
      if (!form.account_name || !form.start_date) { setSubmitting(false); return; }
      const payload = {
        ...form,
        interest_rate: parseFloat(form.interest_rate),
        tenure_years: parseInt(form.tenure_years),
        amount_added: form.payment_type === 'one_time' ? (parseFloat(form.amount_added) || 0) : 0,
        sip_amount: form.payment_type === 'sip' ? (parseFloat(form.sip_amount) || 0) : 0,
        sip_end_date: form.payment_type === 'sip' ? (form.sip_end_date || null) : null,
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
          {isContribution ? `Add Contribution — ${initialData.account_name}` : isEdit ? 'Edit PPF Account' : 'Add PPF Account'}
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
                  <label>Amount (₹) *</label>
                  <input name="amount" type="number" step="1" min="500" max="150000" value={form.amount} onChange={handleChange} placeholder="Min ₹500, Max ₹1,50,000/yr" required />
                </div>
              </div>
              <div className="form-group">
                <label>Remarks</label>
                <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '8px 0' }}>
                PPF yearly limit: ₹1,50,000 per financial year (Apr-Mar). Minimum: ₹500/year.
              </div>
            </>
          ) : (
            <>
              <div className="form-row">
                <div className="form-group">
                  <label>Account Name *</label>
                  <input name="account_name" value={form.account_name} onChange={handleChange} placeholder="e.g. PPF - Self" required autoFocus />
                </div>
                <div className="form-group">
                  <label>Bank / Institution *</label>
                  <input name="bank" value={form.bank} onChange={handleChange} placeholder="e.g. SBI, Post Office" required />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Account Number</label>
                  <input name="account_number" value={form.account_number} onChange={handleChange} placeholder="Optional" />
                </div>
                <div className="form-group">
                  <label>Interest Rate (%) *</label>
                  <input name="interest_rate" type="number" step="0.01" min="0.01" max="15" value={form.interest_rate} onChange={handleChange} required />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Current GOI rate: 7.1%</span>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Start Date *</label>
                  <input name="start_date" type="date" value={form.start_date} onChange={handleChange} required />
                </div>
                <div className="form-group">
                  <label>Tenure (years)</label>
                  <input name="tenure_years" type="number" min="15" max="50" value={form.tenure_years} onChange={handleChange} />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Min 15 years, extendable in 5-yr blocks</span>
                </div>
              </div>

              <div className="form-group">
                <label>Payment Type</label>
                <div style={{ display: 'flex', gap: '0', borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border)' }}>
                  {[{ val: 'one_time', lbl: 'One-time' }, { val: 'sip', lbl: 'SIP (Recurring)' }].map(opt => (
                    <button key={opt.val} type="button" onClick={() => setForm(prev => ({ ...prev, payment_type: opt.val }))}
                      style={{
                        flex: 1, padding: '8px 12px', border: 'none', cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                        background: form.payment_type === opt.val ? 'var(--blue)' : 'var(--bg-input)',
                        color: form.payment_type === opt.val ? '#fff' : 'var(--text-dim)',
                        transition: 'all 0.15s',
                      }}>
                      {opt.lbl}
                    </button>
                  ))}
                </div>
              </div>

              {form.payment_type === 'one_time' ? (
                <div className="form-group">
                  <label>Amount ({'\u20B9'})</label>
                  <input name="amount_added" type="number" step="1" min="0" max="150000" value={form.amount_added} onChange={handleChange} placeholder="Deposit amount (optional)" />
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Creates an opening contribution on the start date</span>
                </div>
              ) : (
                <>
                  <div className="form-row">
                    <div className="form-group">
                      <label>SIP Amount ({'\u20B9'}) *</label>
                      <input name="sip_amount" type="number" step="100" min="500" value={form.sip_amount} onChange={handleChange} placeholder="e.g. 12500" />
                    </div>
                    <div className="form-group">
                      <label>Frequency</label>
                      <select name="sip_frequency" value={form.sip_frequency} onChange={handleChange}>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                        <option value="yearly">Yearly</option>
                      </select>
                    </div>
                  </div>
                  <div className="form-group">
                    <label>SIP End Date (optional)</label>
                    <input name="sip_end_date" type="date" value={form.sip_end_date} onChange={handleChange} />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Leave empty for ongoing until maturity</span>
                  </div>
                </>
              )}

              <div className="form-group">
                <label>Remarks</label>
                <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
              </div>

              {/* Projection Preview */}
              {maturityCalc && (
                <div style={{
                  background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
                  textAlign: 'center', marginTop: '8px',
                }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                    Projection assuming max ₹1.5L/year for {form.tenure_years} years at {form.interest_rate}%
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'center', gap: '32px' }}>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Total Deposited</div>
                      <div style={{ fontSize: '18px', fontWeight: 700 }}>{formatINR(maturityCalc.total_deposited)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Interest Earned</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--green)' }}>{formatINR(maturityCalc.total_interest)}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Maturity Value</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--blue)' }}>{formatINR(maturityCalc.projected_balance)}</div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isContribution ? '+ Add Contribution' : isEdit ? 'Update PPF' : '+ Add PPF'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
