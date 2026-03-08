import React, { useState, useEffect, useRef, useCallback } from 'react';
import { searchStock, fetchStockPrice } from '../services/api';
import html2canvas from 'html2canvas';

const formatINR = (num) => {
  if (num === null || num === undefined || isNaN(num)) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const todayStr = () => {
  const d = new Date();
  const dd = String(d.getDate()).padStart(2, '0');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${dd}-${months[d.getMonth()]}-${d.getFullYear()}`;
};

export default function BuyPlannerModal({ stocks, onClose }) {
  const [rows, setRows] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [fetchingPrice, setFetchingPrice] = useState(null); // symbol being fetched
  const [generating, setGenerating] = useState(false);
  const captureRef = useRef(null);
  const searchDebounceRef = useRef(null);
  const searchInputRef = useRef(null);

  // Pre-populate from portfolio stocks (held only)
  useEffect(() => {
    if (!stocks || stocks.length === 0) return;
    const held = stocks.filter(s => s.total_held_qty > 0);
    const initial = held.map(s => ({
      symbol: s.symbol,
      exchange: s.exchange,
      name: s.name,
      onHand: s.total_held_qty,
      low: s.live?.week_52_low || 0,
      current: s.live?.current_price || 0,
      high: s.live?.week_52_high || 0,
      buyQty: '',
    }));
    // Sort alphabetically
    initial.sort((a, b) => a.symbol.localeCompare(b.symbol));
    setRows(initial);
  }, [stocks]);

  // Filter existing rows by search query (instant, local)
  const filteredRows = searchQuery.trim()
    ? rows.filter(r => {
        const q = searchQuery.trim().toLowerCase();
        return r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q);
      })
    : rows;

  // Debounced API search for adding NEW stocks not in the list
  const handleSearchChange = useCallback((e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    if (!q.trim() || q.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    searchDebounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchStock(q.trim());
        // Filter out stocks already in rows
        const existingSymbols = new Set(rows.map(r => r.symbol));
        setSearchResults(results.filter(r => !existingSymbols.has(r.symbol)));
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 400);
  }, [rows]);

  // Clear search
  const clearSearch = () => {
    setSearchQuery('');
    setSearchResults([]);
  };

  // Add stock from search results
  const handleAddStock = async (result) => {
    setFetchingPrice(result.symbol);
    setSearchQuery('');
    setSearchResults([]);
    try {
      const price = await fetchStockPrice(result.symbol, result.exchange);
      setRows(prev => [{
        symbol: result.symbol,
        exchange: result.exchange,
        name: price.name || result.name,
        onHand: 0,
        low: price.week_52_low || 0,
        current: price.current_price || 0,
        high: price.week_52_high || 0,
        buyQty: '',
      }, ...prev]);
    } catch {
      setRows(prev => [{
        symbol: result.symbol,
        exchange: result.exchange,
        name: result.name,
        onHand: 0,
        low: 0,
        current: 0,
        high: 0,
        buyQty: '',
      }, ...prev]);
    } finally {
      setFetchingPrice(null);
    }
  };

  // Update buy qty for a row
  const updateBuyQty = (idx, value) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, buyQty: value } : r));
  };

  // Remove a row
  const removeRow = (idx) => {
    setRows(prev => prev.filter((_, i) => i !== idx));
  };

  // Computed totals
  const grandTotal = rows.reduce((sum, r) => {
    const qty = parseInt(r.buyQty) || 0;
    return sum + qty * r.current;
  }, 0);

  const rowsWithQty = rows.filter(r => parseInt(r.buyQty) > 0);

  // Generate and download image
  const handleDownload = async () => {
    if (rowsWithQty.length === 0) return;
    setGenerating(true);
    try {
      // Wait a tick for the capture div to render
      await new Promise(r => setTimeout(r, 100));
      const canvas = await html2canvas(captureRef.current, {
        backgroundColor: '#1a1a2e',
        scale: 2,
      });
      const link = document.createElement('a');
      link.download = `buy-plan-${new Date().toISOString().split('T')[0]}.png`;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (err) {
      console.error('Image generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ overflow: 'auto', padding: '24px 0' }}>
      <div
        className="modal"
        style={{ maxWidth: '960px', width: '95vw', maxHeight: '90vh', overflow: 'hidden', margin: 'auto', padding: 0, display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky header: title + search */}
        <div style={{ padding: '24px 28px 0', flexShrink: 0 }}>
          <h2 style={{ marginBottom: '12px' }}>Buy Planner</h2>
          {/* Search input with clear button */}
          <div style={{ position: 'relative', marginBottom: '12px' }}>
            <input
              ref={searchInputRef}
              type="text"
              value={searchQuery}
              onChange={handleSearchChange}
              placeholder="Search / filter stocks or add new..."
              style={{
                width: '100%',
                padding: '8px 32px 8px 12px',
                background: 'var(--surface)',
                border: '1px solid var(--border)',
                borderRadius: '6px',
                color: 'var(--text)',
                fontSize: '13px',
                boxSizing: 'border-box',
              }}
            />
            {searchQuery && (
              <button
                onClick={clearSearch}
                style={{
                  position: 'absolute',
                  right: '8px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted)',
                  cursor: 'pointer',
                  fontSize: '16px',
                  padding: '0 4px',
                  lineHeight: 1,
                }}
                title="Clear search"
              >
                ×
              </button>
            )}
          </div>
          {/* API search results for adding new stocks (inline, not absolute) */}
          {(searchResults.length > 0 || searching || fetchingPrice) && (
            <div style={{
              background: 'var(--surface)',
              border: '1px solid var(--border)',
              borderRadius: '6px',
              marginBottom: '12px',
              maxHeight: '160px',
              overflowY: 'auto',
            }}>
              {fetchingPrice && (
                <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Fetching price for {fetchingPrice}...
                </div>
              )}
              {searching && !fetchingPrice && (
                <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Searching...
                </div>
              )}
              {searchResults.map((r) => (
                <div
                  key={`${r.symbol}-${r.exchange}`}
                  onClick={() => handleAddStock(r)}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    fontSize: '13px',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <span style={{ fontWeight: 600 }}>{r.symbol}</span>
                  <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>
                    {r.name} · {r.exchange}
                  </span>
                  <span style={{ float: 'right', fontSize: '11px', color: 'var(--green)' }}>+ Add</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Scrollable table */}
        <div style={{ overflow: 'auto', flex: 1, padding: '0 28px', borderTop: '1px solid var(--border)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                <th style={thStyle}>Stock</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>On Hand</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>52W Low</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>CMP</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>52W High</th>
                <th style={{ ...thStyle, textAlign: 'right', width: '90px' }}>Buy Qty</th>
                <th style={{ ...thStyle, textAlign: 'right' }}>Est. Amount</th>
                <th style={{ ...thStyle, width: '30px' }}></th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => {
                const idx = rows.findIndex(r => r.symbol === row.symbol && r.exchange === row.exchange);
                const qty = parseInt(row.buyQty) || 0;
                const amount = qty * row.current;
                const dimmed = !qty;
                return (
                  <tr
                    key={`${row.symbol}-${row.exchange}`}
                    style={{
                      borderBottom: '1px solid var(--border)',
                      opacity: dimmed ? 0.5 : 1,
                      transition: 'opacity 0.2s',
                    }}
                  >
                    <td style={tdStyle}>
                      <div style={{ fontWeight: 600 }}>{row.symbol}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {row.name} · {row.exchange}
                      </div>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {row.onHand || '--'}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {row.low ? formatINR(row.low) : '--'}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                      {row.current ? formatINR(row.current) : '--'}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                      {row.high ? formatINR(row.high) : '--'}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <input
                        type="number"
                        min="0"
                        value={row.buyQty}
                        onChange={(e) => updateBuyQty(idx, e.target.value)}
                        placeholder="0"
                        style={{
                          width: '80px',
                          padding: '4px 8px',
                          background: 'var(--surface)',
                          border: '1px solid var(--border)',
                          borderRadius: '4px',
                          color: 'var(--text)',
                          textAlign: 'right',
                          fontSize: '13px',
                        }}
                      />
                    </td>
                    <td style={{
                      ...tdStyle,
                      textAlign: 'right',
                      fontWeight: qty ? 600 : 400,
                      color: qty ? 'var(--green)' : 'var(--text-muted)',
                      fontVariantNumeric: 'tabular-nums',
                    }}>
                      {qty ? formatINR(amount) : '--'}
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      {row.onHand === 0 && (
                        <button
                          onClick={() => removeRow(idx)}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer',
                            fontSize: '14px',
                            padding: '2px',
                          }}
                          title="Remove"
                        >
                          x
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {/* No matches message */}
              {filteredRows.length === 0 && searchQuery.trim() && (
                <tr>
                  <td colSpan={8} style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                    No matching stocks — select from dropdown to add new
                  </td>
                </tr>
              )}
              {/* Grand total row */}
              {filteredRows.length > 0 && (
                <tr style={{ borderTop: '2px solid var(--border)' }}>
                  <td colSpan={6} style={{ ...tdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>
                    Grand Total
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, color: 'var(--green)', fontVariantNumeric: 'tabular-nums' }}>
                    {grandTotal > 0 ? formatINR(grandTotal) : '--'}
                  </td>
                  <td></td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Sticky footer: actions */}
        <div style={{ padding: '16px 28px', borderTop: '1px solid var(--border)', flexShrink: 0, display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          <button
            className="btn btn-primary"
            onClick={handleDownload}
            disabled={generating || rowsWithQty.length === 0}
          >
            {generating ? 'Generating...' : 'Download Image'}
          </button>
        </div>

        {/* Hidden capture div for image generation */}
        {rowsWithQty.length > 0 && (
          <div style={{ position: 'absolute', left: '-9999px', top: 0 }}>
            <div
              ref={captureRef}
              style={{
                background: '#1a1a2e',
                color: '#e0e0e0',
                padding: '24px 28px',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                width: '860px',
              }}
            >
              {/* Title */}
              <div style={{ marginBottom: '16px' }}>
                <div style={{ fontSize: '18px', fontWeight: 700, color: '#ffffff' }}>
                  Buy Plan — {todayStr()}
                </div>
              </div>

              {/* Table */}
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #333355' }}>
                    <th style={capThStyle}>Stock</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>On Hand</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>52W Low</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>CMP</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>52W High</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>Buy Qty</th>
                    <th style={{ ...capThStyle, textAlign: 'right' }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {rowsWithQty.map((row) => {
                    const qty = parseInt(row.buyQty) || 0;
                    const amount = qty * row.current;
                    return (
                      <tr key={row.symbol} style={{ borderBottom: '1px solid #2a2a45' }}>
                        <td style={capTdStyle}>
                          <span style={{ fontWeight: 600 }}>{row.symbol}</span>
                          <span style={{ color: '#888', marginLeft: '6px', fontSize: '11px' }}>
                            {row.exchange}
                          </span>
                        </td>
                        <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.onHand || '--'}</td>
                        <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.low ? formatINR(row.low) : '--'}</td>
                        <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(row.current)}</td>
                        <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.high ? formatINR(row.high) : '--'}</td>
                        <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>{qty}</td>
                        <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600, color: '#4ade80' }}>
                          {formatINR(amount)}
                        </td>
                      </tr>
                    );
                  })}
                  {/* Grand total */}
                  <tr style={{ borderTop: '2px solid #333355' }}>
                    <td colSpan={6} style={{ ...capTdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>
                      Grand Total
                    </td>
                    <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, color: '#4ade80', fontSize: '14px' }}>
                      {formatINR(grandTotal)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const thStyle = {
  padding: '8px 6px',
  fontSize: '12px',
  fontWeight: 600,
  color: 'var(--text-muted)',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
};

const tdStyle = {
  padding: '8px 6px',
};

const capThStyle = {
  padding: '8px 6px',
  fontSize: '11px',
  fontWeight: 600,
  color: '#888',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  textAlign: 'left',
};

const capTdStyle = {
  padding: '8px 6px',
  fontVariantNumeric: 'tabular-nums',
};
