import React, { useState } from 'react';

export default function DividendModal({ symbol, exchange, onSubmit, onClose }) {
  const today = new Date().toISOString().split('T')[0];
  const [amount, setAmount] = useState('');
  const [dividendDate, setDividendDate] = useState(today);
  const [remarks, setRemarks] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!amount || parseFloat(amount) <= 0) return;
    setSubmitting(true);
    try {
      await onSubmit({
        symbol,
        exchange,
        amount: parseFloat(amount),
        dividend_date: dividendDate,
        remarks,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '420px' }}>
        <div className="modal-header">
          <h3>Record Dividend — {symbol}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Dividend Amount (₹)</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="e.g. 500.00"
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label>Date</label>
            <input
              type="date"
              value={dividendDate}
              onChange={(e) => setDividendDate(e.target.value)}
              required
            />
          </div>
          <div className="form-group">
            <label>Remarks (optional)</label>
            <input
              type="text"
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="e.g. Interim dividend Q3"
            />
          </div>
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={submitting || !amount || parseFloat(amount) <= 0}
            >
              {submitting ? 'Recording...' : 'Record Dividend'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
