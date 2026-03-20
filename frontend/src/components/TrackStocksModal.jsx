import React, { useState, useRef, useCallback } from 'react';
import useEscapeKey from '../hooks/useEscapeKey';
import { searchUntracked, trackStocks, lookupStockName } from '../services/api';
import toast from 'react-hot-toast';

export default function TrackStocksModal({ onClose, onAdded }) {
  useEscapeKey(onClose);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(new Map()); // symbol → {symbol, exchange, name}
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [manualSymbol, setManualSymbol] = useState('');
  const [manualExchange, setManualExchange] = useState('NSE');
  const [addingManual, setAddingManual] = useState(false);
  const debounceRef = useRef(null);

  const handleSearch = useCallback((q) => {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) { setResults([]); return; }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await searchUntracked(q.trim());
        setResults(data);
      } catch { setResults([]); }
      setLoading(false);
    }, 300);
  }, []);

  const toggleSelect = (item) => {
    setSelected(prev => {
      const next = new Map(prev);
      if (next.has(item.symbol)) next.delete(item.symbol);
      else next.set(item.symbol, item);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(prev => {
      const next = new Map(prev);
      results.forEach(r => next.set(r.symbol, r));
      return next;
    });
  };

  const clearAll = () => setSelected(new Map());

  const handleAddManual = async () => {
    const sym = manualSymbol.trim().toUpperCase();
    if (!sym) return;
    if (selected.has(sym)) {
      toast.error(`${sym} already selected`);
      return;
    }
    setAddingManual(true);
    let name = sym;
    try {
      const info = await lookupStockName(sym);
      if (info?.name) name = info.name;
    } catch {}
    setSelected(prev => {
      const next = new Map(prev);
      next.set(sym, { symbol: sym, exchange: manualExchange, name });
      return next;
    });
    setManualSymbol('');
    setAddingManual(false);
    toast.success(`${sym} added to selection`);
  };

  const handleSubmit = async () => {
    if (selected.size === 0) return;
    setSubmitting(true);
    try {
      const symbols = Array.from(selected.values());
      const result = await trackStocks(symbols);
      toast.success(`Added ${result.count} stock${result.count !== 1 ? 's' : ''} to watchlist`);
      onAdded?.();
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add stocks');
    }
    setSubmitting(false);
  };

  const modalStyle = {
    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
    background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', zIndex: 1000,
  };
  const boxStyle = {
    background: 'var(--bg-card)', border: '1px solid var(--border)',
    borderRadius: '12px', padding: '24px', width: '560px', maxHeight: '85vh',
    display: 'flex', flexDirection: 'column', gap: '14px',
  };
  const inputStyle = {
    padding: '9px 12px', fontSize: '13px', borderRadius: '6px',
    border: '1px solid var(--border)', background: 'var(--bg)',
    color: 'var(--text)', outline: 'none', boxSizing: 'border-box',
  };

  return (
    <div style={modalStyle} onClick={onClose}>
      <div style={boxStyle} onClick={e => e.stopPropagation()}>
        <h2 style={{ margin: 0, fontSize: '18px', color: 'var(--text)' }}>Add to Watchlist</h2>
        <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted)' }}>
          Search stocks not in your portfolio, or add manually by symbol
        </p>

        {/* Search */}
        <input
          type="text"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          placeholder="Search by symbol or company name..."
          autoFocus
          style={{ ...inputStyle, width: '100%', fontSize: '14px', padding: '10px 14px' }}
        />

        {/* Manual add row */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            type="text"
            value={manualSymbol}
            onChange={e => setManualSymbol(e.target.value.toUpperCase())}
            onKeyDown={e => e.key === 'Enter' && handleAddManual()}
            placeholder="Symbol (e.g. RELIANCE)"
            style={{ ...inputStyle, flex: 1 }}
          />
          <select
            value={manualExchange}
            onChange={e => setManualExchange(e.target.value)}
            style={{ ...inputStyle, width: '80px' }}
          >
            <option value="NSE">NSE</option>
            <option value="BSE">BSE</option>
          </select>
          <button
            onClick={handleAddManual}
            disabled={!manualSymbol.trim() || addingManual}
            style={{
              padding: '9px 14px', borderRadius: '6px', border: 'none',
              background: manualSymbol.trim() ? 'var(--blue)' : 'var(--border)',
              color: '#fff', cursor: manualSymbol.trim() ? 'pointer' : 'default',
              fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap',
            }}
          >
            {addingManual ? '...' : '+ Add'}
          </button>
        </div>

        {/* Selected chips */}
        {selected.size > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
            {Array.from(selected.values()).map(s => (
              <span key={s.symbol} style={{
                display: 'inline-flex', alignItems: 'center', gap: '4px',
                padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 600,
                background: 'rgba(74,144,226,0.15)', color: 'var(--blue)',
              }}>
                {s.symbol}
                <span
                  onClick={() => toggleSelect(s)}
                  style={{ cursor: 'pointer', opacity: 0.6, fontSize: '13px' }}
                >&times;</span>
              </span>
            ))}
            <button onClick={clearAll} style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', fontSize: '11px', textDecoration: 'underline',
            }}>Clear all</button>
          </div>
        )}

        {/* Results list */}
        <div style={{
          flex: 1, overflowY: 'auto', minHeight: '180px', maxHeight: '350px',
          border: '1px solid var(--border)', borderRadius: '8px', background: 'var(--bg)',
        }}>
          {loading && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              Searching...
            </div>
          )}
          {!loading && query && results.length === 0 && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              No untracked stocks found for "{query}"
              <div style={{ marginTop: '8px', fontSize: '11px' }}>
                Use the manual add above to add by symbol
              </div>
            </div>
          )}
          {!loading && !query && (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
              Type to search NSE/BSE stocks
            </div>
          )}
          {!loading && results.length > 0 && (
            <>
              <div style={{
                padding: '6px 12px', borderBottom: '1px solid var(--border)',
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {results.length} results
                </span>
                <button onClick={selectAll} style={{
                  background: 'none', border: 'none', color: 'var(--blue)',
                  cursor: 'pointer', fontSize: '11px',
                }}>Select all</button>
              </div>
              {results.map(r => {
                const isSelected = selected.has(r.symbol);
                return (
                  <div
                    key={`${r.symbol}.${r.exchange}`}
                    onClick={() => toggleSelect(r)}
                    style={{
                      padding: '7px 12px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: '10px',
                      background: isSelected ? 'rgba(74,144,226,0.1)' : 'transparent',
                      borderBottom: '1px solid var(--border)',
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleSelect(r)}
                      style={{ accentColor: 'var(--blue)', cursor: 'pointer' }}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                        {r.symbol}
                        <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: '6px', fontSize: '11px' }}>
                          {r.exchange}
                        </span>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{r.name}</div>
                    </div>
                  </div>
                );
              })}
            </>
          )}
        </div>

        {/* Actions */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
          <button onClick={onClose} style={{
            padding: '8px 20px', borderRadius: '6px', border: '1px solid var(--border)',
            background: 'transparent', color: 'var(--text)', cursor: 'pointer', fontSize: '13px',
          }}>Cancel</button>
          <button
            onClick={handleSubmit}
            disabled={selected.size === 0 || submitting}
            style={{
              padding: '8px 20px', borderRadius: '6px', border: 'none',
              background: selected.size > 0 ? 'var(--blue)' : 'var(--border)',
              color: '#fff', cursor: selected.size > 0 ? 'pointer' : 'default',
              fontSize: '13px', fontWeight: 600, opacity: submitting ? 0.7 : 1,
            }}
          >
            {submitting ? 'Adding...' : `Add ${selected.size} to Watchlist`}
          </button>
        </div>
      </div>
    </div>
  );
}
