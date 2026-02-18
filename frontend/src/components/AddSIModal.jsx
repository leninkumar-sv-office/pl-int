import React, { useState } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddSIModal({ onAdd, onClose, initialData }) {
  const isEdit = !!(initialData?.id);
  const [form, setForm] = useState({
    bank: initialData?.bank || '',
    beneficiary: initialData?.beneficiary || '',
    amount: initialData?.amount || '',
    frequency: initialData?.frequency || 'Monthly',
    purpose: initialData?.purpose || 'SIP',
    mandate_type: initialData?.mandate_type || 'NACH',
    account_number: initialData?.account_number || '',
    start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
    expiry_date: initialData?.expiry_date || '',
    alert_days: initialData?.alert_days || 30,
    status: initialData?.status || 'Active',
    remarks: initialData?.remarks || '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.bank || !form.beneficiary || !form.amount || !form.start_date || !form.expiry_date) return;
    setSubmitting(true);
    const payload = {
      ...form,
      amount: parseFloat(form.amount),
      alert_days: parseInt(form.alert_days) || 30,
    };
    if (isEdit) payload.id = initialData.id;
    await onAdd(payload);
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit Standing Instruction' : 'Add Standing Instruction'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Bank *</label>
              <input name="bank" value={form.bank} onChange={handleChange}
                placeholder="e.g. HDFC Bank, SBI" required autoFocus />
            </div>
            <div className="form-group">
              <label>Beneficiary *</label>
              <input name="beneficiary" value={form.beneficiary} onChange={handleChange}
                placeholder="e.g. SBI MF, ICICI Prudential" required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Amount (₹) *</label>
              <input name="amount" type="number" step="0.01" min="1" value={form.amount} onChange={handleChange}
                placeholder="Debit amount" required />
            </div>
            <div className="form-group">
              <label>Frequency</label>
              <select name="frequency" value={form.frequency} onChange={handleChange}>
                <option value="Monthly">Monthly</option>
                <option value="Quarterly">Quarterly</option>
                <option value="Half-Yearly">Half-Yearly</option>
                <option value="Annually">Annually</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Purpose</label>
              <select name="purpose" value={form.purpose} onChange={handleChange}>
                <option value="SIP">SIP</option>
                <option value="EMI">EMI</option>
                <option value="Utility">Utility</option>
                <option value="Insurance">Insurance</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div className="form-group">
              <label>Mandate Type</label>
              <select name="mandate_type" value={form.mandate_type} onChange={handleChange}>
                <option value="NACH">NACH</option>
                <option value="ECS">ECS</option>
                <option value="UPI Autopay">UPI Autopay</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Account Number</label>
            <input name="account_number" value={form.account_number} onChange={handleChange}
              placeholder="Optional" />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Start Date *</label>
              <input name="start_date" type="date" value={form.start_date} onChange={handleChange} required />
            </div>
            <div className="form-group">
              <label>Expiry Date *</label>
              <input name="expiry_date" type="date" value={form.expiry_date} onChange={handleChange} required />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Alert Before (days)</label>
              <input name="alert_days" type="number" min="1" value={form.alert_days} onChange={handleChange}
                placeholder="30" />
            </div>
            <div className="form-group">
              <label>Status</label>
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="Active">Active</option>
                <option value="Expired">Expired</option>
                <option value="Cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Remarks</label>
            <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
          </div>

          {/* Summary */}
          {form.amount && parseFloat(form.amount) > 0 && (
            <div style={{
              background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
              textAlign: 'center', marginTop: '8px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '32px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Amount ({form.frequency})</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text)' }}>{formatINR(parseFloat(form.amount))}</div>
                </div>
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEdit ? 'Update SI' : '+ Add SI'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
