import React, { useState } from 'react';
import useEscapeKey from '../hooks/useEscapeKey';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

/**
 * Reusable modal for editing a held or sold lot.
 *
 * Props:
 *   title: e.g. "Edit Held Lot — TATAPOWER" or "Edit Sold Lot — RELIANCE"
 *   fields: array of { key, label, type, value, step?, min?, max? }
 *   onSave: async (updates: {key: value}) => void
 *   onClose: () => void
 */
export default function EditLotModal({ title, fields, onSave, onClose }) {
  useEscapeKey(onClose);
  const [values, setValues] = useState(
    Object.fromEntries(fields.map(f => [f.key, f.value ?? '']))
  );
  const [saving, setSaving] = useState(false);

  const handleChange = (key, val) => {
    setValues(prev => ({ ...prev, [key]: val }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await onSave(values);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '420px' }}>
        <h2 style={{ fontSize: '16px', marginBottom: '16px' }}>{title}</h2>

        <form onSubmit={handleSubmit}>
          {fields.map(f => (
            <div key={f.key} className="form-group" style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px', display: 'block' }}>
                {f.label}
              </label>
              <input
                type={f.type || 'text'}
                step={f.step}
                min={f.min}
                max={f.max}
                value={values[f.key]}
                onChange={(e) => handleChange(f.key, e.target.value)}
                required
                style={{
                  width: '100%', padding: '8px 12px', fontSize: '13px',
                  background: 'var(--bg-input)', color: 'var(--text)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                  outline: 'none',
                }}
              />
            </div>
          ))}

          <div className="modal-actions" style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '16px' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={saving}
              style={{
                background: 'var(--blue)', color: '#fff', border: 'none',
                padding: '8px 20px', borderRadius: 'var(--radius-sm)',
                fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.6 : 1,
              }}>
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
