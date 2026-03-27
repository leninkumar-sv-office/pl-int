import React, { useState, useEffect, useRef } from 'react';
import useEscapeKey from '../hooks/useEscapeKey';
import { lookupStockName, searchStock } from '../services/api';

export default function AddStockModal({ onAdd, onClose, initialData }) {
  useEscapeKey(onClose);
  const [form, setForm] = useState({
    symbol: initialData?.symbol || '',
    exchange: initialData?.exchange || 'NSE',
    name: initialData?.name || '',
    quantity: '',
    buy_price: '',
    buy_date: new Date().toISOString().split('T')[0],
    notes: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightIdx, setHighlightIdx] = useState(-1);
  const debounceRef = useRef(null);

  // Debounced search: when symbol changes, search after 200ms pause
  useEffect(() => {
    if (justSelectedRef.current) { justSelectedRef.current = false; return; }
    const sym = form.symbol.trim();
    if (!sym || sym.length < 2) {
      setSuggestions([]);
      return;
    }

    if (debounceRef.current) clearTimeout(debounceRef.current);

    debounceRef.current = setTimeout(async () => {
      try {
        const results = await searchStock(sym, form.exchange);
        if (Array.isArray(results)) {
          // Sort: exact symbol match first, then starts-with symbol, then name matches
          const q = sym.toUpperCase();
          results.sort((a, b) => {
            const aExact = a.symbol === q ? 0 : 1;
            const bExact = b.symbol === q ? 0 : 1;
            if (aExact !== bExact) return aExact - bExact;
            const aStarts = a.symbol.startsWith(q) ? 0 : 1;
            const bStarts = b.symbol.startsWith(q) ? 0 : 1;
            if (aStarts !== bStarts) return aStarts - bStarts;
            return a.symbol.localeCompare(b.symbol);
          });
          setSuggestions(results.slice(0, 15));
          setShowSuggestions(true);
        }
      } catch {
        setSuggestions([]);
      }
    }, 200);

    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [form.symbol, form.exchange]);

  // Reset highlight when suggestions change
  useEffect(() => { setHighlightIdx(-1); }, [suggestions]);

  const justSelectedRef = useRef(false);
  const selectSuggestion = (s) => {
    justSelectedRef.current = true;
    setForm(prev => ({ ...prev, symbol: s.symbol, name: s.name, exchange: s.exchange || prev.exchange }));
    setSuggestions([]);
    setShowSuggestions(false);
    setHighlightIdx(-1);
  };

  const handleSymbolKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Escape') { setSuggestions([]); setShowSuggestions(false); }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(prev => (prev + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(prev => (prev - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter') {
      if (highlightIdx >= 0) {
        e.preventDefault();
        e.stopPropagation();
        selectSuggestion(suggestions[highlightIdx]);
      } else if (suggestions.length > 0) {
        // Select first suggestion if none highlighted
        e.preventDefault();
        e.stopPropagation();
        selectSuggestion(suggestions[0]);
      }
    } else if (e.key === 'Escape') {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleChange = (e) => {
    const { name, value } = e.target;
    if (name === 'symbol') {
      setForm(prev => ({ ...prev, symbol: value.toUpperCase(), name: '' }));
    } else {
      setForm(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.symbol) return;
    setSubmitting(true);
    await onAdd({
      ...form,
      symbol: form.symbol.toUpperCase(),
      quantity: form.quantity ? parseInt(form.quantity) : 0,
      buy_price: form.buy_price ? parseFloat(form.buy_price) : 0,
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Add Stock to Portfolio</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group" style={{ position: 'relative' }}>
              <label>Stock Symbol *</label>
              <input
                name="symbol"
                value={form.symbol}
                onChange={handleChange}
                onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                onKeyDown={handleSymbolKeyDown}
                placeholder="Type to search (e.g. LG, TRIVE)"
                required
                autoFocus
                autoComplete="off"
              />
              {showSuggestions && suggestions.length > 0 && (
                <div style={{
                  position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 200,
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderRadius: '0 0 6px 6px', maxHeight: '200px', overflowY: 'auto',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                }}>
                  {suggestions.map((s, i) => (
                    <div key={i}
                      onClick={() => selectSuggestion(s)}
                      onMouseEnter={() => setHighlightIdx(i)}
                      style={{
                        padding: '8px 12px', cursor: 'pointer', fontSize: '12px',
                        borderBottom: '1px solid var(--border)',
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                        background: i === highlightIdx ? 'rgba(59,130,246,0.15)' : 'transparent',
                      }}
                    >
                      <span><strong>{s.symbol}</strong> <span style={{ color: 'var(--text-muted)' }}>{s.name}</span></span>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{s.exchange}</span>
                    </div>
                  ))}
                </div>
              )}
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
            <label>
              Company Name
              {!form.name && form.symbol.length >= 2 && (
                <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
                  Select from suggestions above
                </span>
              )}
            </label>
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="Auto-populated from Zerodha"
              style={{
                borderColor: form.name ? 'var(--green)' : undefined,
                transition: 'border-color 0.2s',
              }}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Quantity</label>
              <input
                name="quantity"
                type="number"
                min="0"
                value={form.quantity}
                onChange={handleChange}
                placeholder="0 to just track"
              />
            </div>
            <div className="form-group">
              <label>Buy Price (₹)</label>
              <input
                name="buy_price"
                type="number"
                step="0.01"
                min="0"
                value={form.buy_price}
                onChange={handleChange}
                placeholder="0 to just track"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Buy Date</label>
              <input
                name="buy_date"
                type="date"
                value={form.buy_date}
                onChange={handleChange}
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
