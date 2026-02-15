import React, { useState } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddInsuranceModal({ onAdd, onClose, initialData }) {
  const isEdit = !!(initialData?.id);
  const [form, setForm] = useState({
    policy_name: initialData?.policy_name || '',
    provider: initialData?.provider || '',
    type: initialData?.type || 'Health',
    policy_number: initialData?.policy_number || '',
    premium: initialData?.premium || '',
    coverage_amount: initialData?.coverage_amount || '',
    start_date: initialData?.start_date || new Date().toISOString().split('T')[0],
    expiry_date: initialData?.expiry_date || '',
    payment_frequency: initialData?.payment_frequency || 'Annual',
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
    if (!form.policy_name || !form.provider || !form.premium || !form.start_date || !form.expiry_date) return;
    setSubmitting(true);
    const payload = {
      ...form,
      premium: parseFloat(form.premium),
      coverage_amount: parseFloat(form.coverage_amount) || 0,
    };
    if (isEdit) payload.id = initialData.id;
    await onAdd(payload);
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit Insurance Policy' : 'Add Insurance Policy'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Policy Name *</label>
            <input name="policy_name" value={form.policy_name} onChange={handleChange}
              placeholder="e.g. Star Health Family Plan" required autoFocus />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Provider *</label>
              <input name="provider" value={form.provider} onChange={handleChange}
                placeholder="e.g. Star Health, ICICI Lombard" required />
            </div>
            <div className="form-group">
              <label>Type</label>
              <select name="type" value={form.type} onChange={handleChange}>
                <option value="Health">Health</option>
                <option value="Life">Life</option>
                <option value="Car">Car</option>
                <option value="Bike">Bike</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Policy Number</label>
              <input name="policy_number" value={form.policy_number} onChange={handleChange}
                placeholder="Optional" />
            </div>
            <div className="form-group">
              <label>Payment Frequency</label>
              <select name="payment_frequency" value={form.payment_frequency} onChange={handleChange}>
                <option value="Monthly">Monthly</option>
                <option value="Quarterly">Quarterly</option>
                <option value="Annual">Annual</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Premium (₹) *</label>
              <input name="premium" type="number" step="0.01" min="1" value={form.premium} onChange={handleChange}
                placeholder="Premium amount" required />
            </div>
            <div className="form-group">
              <label>Coverage / Sum Assured (₹)</label>
              <input name="coverage_amount" type="number" step="0.01" min="0" value={form.coverage_amount} onChange={handleChange}
                placeholder="Sum assured" />
            </div>
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
              <label>Status</label>
              <select name="status" value={form.status} onChange={handleChange}>
                <option value="Active">Active</option>
                <option value="Expired">Expired</option>
                <option value="Cancelled">Cancelled</option>
              </select>
            </div>
            <div className="form-group">
              <label>Remarks</label>
              <input name="remarks" value={form.remarks} onChange={handleChange} placeholder="Optional notes" />
            </div>
          </div>

          {/* Premium Summary */}
          {form.premium && parseFloat(form.premium) > 0 && (
            <div style={{
              background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px',
              textAlign: 'center', marginTop: '8px',
            }}>
              <div style={{ display: 'flex', justifyContent: 'center', gap: '32px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Premium ({form.payment_frequency})</div>
                  <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text)' }}>{formatINR(parseFloat(form.premium))}</div>
                </div>
                {form.coverage_amount && parseFloat(form.coverage_amount) > 0 && (
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Coverage</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--blue)' }}>{formatINR(parseFloat(form.coverage_amount))}</div>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEdit ? 'Update Policy' : '+ Add Policy'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
