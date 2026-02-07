import React, { useState } from 'react';

export default function AddStockModal({ onAdd, onClose }) {
  const [form, setForm] = useState({
    symbol: '',
    exchange: 'NSE',
    name: '',
    quantity: '',
    buy_price: '',
    buy_date: new Date().toISOString().split('T')[0],
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.symbol || !form.quantity || !form.buy_price || !form.buy_date) return;
    setSubmitting(true);
    await onAdd({
      ...form,
      symbol: form.symbol.toUpperCase(),
      quantity: parseInt(form.quantity),
      buy_price: parseFloat(form.buy_price),
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Add Stock to Portfolio</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Stock Symbol *</label>
              <input
                name="symbol"
                value={form.symbol}
                onChange={handleChange}
                placeholder="e.g. RELIANCE"
                required
                autoFocus
              />
            </div>
            <div className="form-group">
              <label>Exchange</label>
              <select name="exchange" value={form.exchange} onChange={handleChange}>
                <option value="NSE">NSE</option>
                <option value="BSE">BSE</option>
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Company Name (auto-fetched if empty)</label>
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="e.g. Reliance Industries"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Quantity *</label>
              <input
                name="quantity"
                type="number"
                min="1"
                value={form.quantity}
                onChange={handleChange}
                placeholder="Number of shares"
                required
              />
            </div>
            <div className="form-group">
              <label>Buy Price (₹) *</label>
              <input
                name="buy_price"
                type="number"
                step="0.01"
                min="0.01"
                value={form.buy_price}
                onChange={handleChange}
                placeholder="Price per share"
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
              <label>Notes</label>
              <input
                name="notes"
                value={form.notes}
                onChange={handleChange}
                placeholder="Optional notes"
              />
            </div>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Adding...' : '+ Add Stock'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
