import React, { useState } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function SIPConfigModal({ fund, existingSIP, onSave, onDelete, onClose }) {
  const fundName = (fund.name || '').replace(/ - Direct Plan.*| - Direct Growth.*| Direct Growth.*/i, '');
  const isEdit = !!existingSIP;

  const [form, setForm] = useState({
    fund_code: fund.fund_code,
    fund_name: fund.name,
    amount: existingSIP?.amount || '',
    frequency: existingSIP?.frequency || 'monthly',
    sip_date: existingSIP?.sip_date || 1,
    start_date: existingSIP?.start_date || new Date().toISOString().split('T')[0],
    end_date: existingSIP?.end_date || '',
    enabled: existingSIP?.enabled ?? true,
    notes: existingSIP?.notes || '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.amount || !form.frequency) return;
    setSubmitting(true);
    await onSave({
      ...form,
      amount: parseFloat(form.amount),
      sip_date: parseInt(form.sip_date),
      end_date: form.end_date || null,
    });
    setSubmitting(false);
  };

  const handleDelete = async () => {
    if (window.confirm('Remove SIP for this fund?')) {
      setSubmitting(true);
      await onDelete(fund.fund_code);
      setSubmitting(false);
    }
  };

  const freqLabel = {
    weekly: 'Day of Week',
    monthly: 'Day of Month',
    quarterly: 'Day of Month',
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit' : 'Setup'} SIP</h2>

        {/* Fund info */}
        <div style={{ background: 'var(--bg-input)', borderRadius: '8px', padding: '12px 16px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--text-dim)' }}>Fund</span>
            <span style={{ fontWeight: 600, fontSize: '13px' }}>{fundName}</span>
          </div>
          {existingSIP && existingSIP.next_sip_date && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '8px' }}>
              <span style={{ color: 'var(--text-dim)' }}>Next SIP Date</span>
              <span style={{ fontWeight: 600, color: 'var(--green)' }}>{existingSIP.next_sip_date}</span>
            </div>
          )}
          {existingSIP && existingSIP.last_processed && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '4px' }}>
              <span style={{ color: 'var(--text-dim)' }}>Last Processed</span>
              <span style={{ color: 'var(--text-muted)' }}>{existingSIP.last_processed}</span>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>SIP Amount (₹) *</label>
              <input
                name="amount"
                type="number"
                step="100"
                min="100"
                value={form.amount}
                onChange={handleChange}
                placeholder="e.g. 5000"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>Frequency *</label>
              <select name="frequency" value={form.frequency} onChange={handleChange}>
                <option value="weekly">Weekly</option>
                <option value="monthly">Monthly</option>
                <option value="quarterly">Quarterly</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>{freqLabel[form.frequency] || 'SIP Date'} *</label>
              {form.frequency === 'weekly' ? (
                <select name="sip_date" value={form.sip_date} onChange={handleChange}>
                  <option value={1}>Monday</option>
                  <option value={2}>Tuesday</option>
                  <option value={3}>Wednesday</option>
                  <option value={4}>Thursday</option>
                  <option value={5}>Friday</option>
                </select>
              ) : (
                <input
                  name="sip_date"
                  type="number"
                  min="1"
                  max="28"
                  value={form.sip_date}
                  onChange={handleChange}
                  required
                />
              )}
            </div>
            <div className="form-group">
              <label>Start Date</label>
              <input
                name="start_date"
                type="date"
                value={form.start_date}
                onChange={handleChange}
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>End Date (optional)</label>
              <input
                name="end_date"
                type="date"
                value={form.end_date}
                onChange={handleChange}
                placeholder="Leave empty for perpetual"
              />
            </div>
            <div className="form-group" style={{ display: 'flex', alignItems: 'center', paddingTop: '20px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <input
                  name="enabled"
                  type="checkbox"
                  checked={form.enabled}
                  onChange={handleChange}
                  style={{ accentColor: 'var(--green)', width: '16px', height: '16px' }}
                />
                Enabled
              </label>
            </div>
          </div>

          <div className="form-group">
            <label>Notes</label>
            <input
              name="notes"
              value={form.notes}
              onChange={handleChange}
              placeholder="Optional notes"
            />
          </div>

          {/* Summary */}
          {form.amount && (
            <div style={{
              background: 'rgba(0,210,106,0.08)',
              borderRadius: '8px',
              padding: '12px 16px',
              textAlign: 'center',
              marginTop: '8px',
              border: '1px solid rgba(0,210,106,0.2)',
            }}>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>
                {form.frequency === 'weekly' ? 'Weekly' : form.frequency === 'quarterly' ? 'Quarterly' : 'Monthly'} SIP
              </div>
              <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--green)' }}>
                {formatINR(parseFloat(form.amount) || 0)}
                <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--text-muted)', marginLeft: '4px' }}>
                  /{form.frequency === 'weekly' ? 'wk' : form.frequency === 'quarterly' ? 'qtr' : 'mo'}
                </span>
              </div>
            </div>
          )}

          <div className="modal-actions" style={{ display: 'flex', gap: '8px' }}>
            {isEdit && (
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDelete}
                disabled={submitting}
                style={{ marginRight: 'auto' }}
              >
                Delete SIP
              </button>
            )}
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Saving...' : isEdit ? 'Update SIP' : 'Setup SIP'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
