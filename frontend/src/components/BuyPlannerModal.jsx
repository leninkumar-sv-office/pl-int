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
  const fileInputRef = useRef(null);

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

  const PLAN_KEY = 'BuyPlan';

  // Insert a tEXt chunk into PNG bytes (proper PNG metadata, survives all file handling)
  const insertPNGTextChunk = (pngBytes, key, value) => {
    const data = new TextEncoder().encode(key + '\0' + value);
    const chunkLen = data.length;
    // tEXt chunk: 4-byte length + "tEXt" + data + 4-byte CRC
    const chunk = new Uint8Array(12 + chunkLen);
    const view = new DataView(chunk.buffer);
    view.setUint32(0, chunkLen); // length
    chunk[4] = 0x74; chunk[5] = 0x45; chunk[6] = 0x58; chunk[7] = 0x74; // "tEXt"
    chunk.set(data, 8);
    // CRC32 over type + data
    const crcData = chunk.slice(4, 8 + chunkLen);
    view.setUint32(8 + chunkLen, crc32(crcData));
    // Insert before IEND (last 12 bytes of a PNG)
    const result = new Uint8Array(pngBytes.length + chunk.length);
    result.set(pngBytes.slice(0, pngBytes.length - 12), 0);
    result.set(chunk, pngBytes.length - 12);
    result.set(pngBytes.slice(pngBytes.length - 12), pngBytes.length - 12 + chunk.length);
    return result;
  };

  // CRC32 for PNG chunks
  const crc32 = (bytes) => {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) {
      crc ^= bytes[i];
      for (let j = 0; j < 8; j++) {
        crc = (crc >>> 1) ^ (crc & 1 ? 0xEDB88320 : 0);
      }
    }
    return (crc ^ 0xFFFFFFFF) >>> 0;
  };

  // Read a tEXt chunk from PNG bytes
  const readPNGTextChunk = (bytes, key) => {
    let offset = 8; // skip PNG signature
    while (offset < bytes.length) {
      const view = new DataView(bytes.buffer, bytes.byteOffset + offset);
      const len = view.getUint32(0);
      const type = new TextDecoder().decode(bytes.slice(offset + 4, offset + 8));
      if (type === 'tEXt') {
        const chunkData = bytes.slice(offset + 8, offset + 8 + len);
        const nullIdx = chunkData.indexOf(0);
        if (nullIdx >= 0) {
          const chunkKey = new TextDecoder().decode(chunkData.slice(0, nullIdx));
          if (chunkKey === key) {
            return new TextDecoder().decode(chunkData.slice(nullIdx + 1));
          }
        }
      }
      if (type === 'IEND') break;
      offset += 12 + len; // 4 len + 4 type + data + 4 crc
    }
    return null;
  };

  // Generate and download image with embedded plan data
  const handleDownload = async () => {
    if (rowsWithQty.length === 0) return;
    setGenerating(true);
    try {
      await new Promise(r => setTimeout(r, 100));
      const canvas = await html2canvas(captureRef.current, {
        backgroundColor: '#1a1a2e',
        scale: 2,
      });
      const dateStr = new Date().toISOString().split('T')[0];
      const planData = rowsWithQty.map(r => ({
        symbol: r.symbol, exchange: r.exchange, buyQty: parseInt(r.buyQty) || 0,
      }));
      const pngBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      const pngBuf = new Uint8Array(await pngBlob.arrayBuffer());
      const withData = insertPNGTextChunk(pngBuf, PLAN_KEY, JSON.stringify(planData));
      const finalBlob = new Blob([withData], { type: 'image/png' });
      const link = document.createElement('a');
      link.download = `buy-plan-${dateStr}.png`;
      link.href = URL.createObjectURL(finalBlob);
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) {
      console.error('Image generation failed:', err);
    } finally {
      setGenerating(false);
    }
  };

  // Extract plan JSON from PNG tEXt chunk
  const extractPlanFromPNG = (arrayBuffer) => {
    const bytes = new Uint8Array(arrayBuffer);
    const json = readPNGTextChunk(bytes, PLAN_KEY);
    if (!json) return null;
    return JSON.parse(json);
  };

  // Import plan data into rows
  const importPlanData = async (planData) => {
    if (!Array.isArray(planData) || planData.length === 0) return;
    // Fetch prices for new stocks first, then do a single setRows update
    const newStocks = [];
    // We need current rows — read via ref-style trick
    let currentRows = [];
    setRows(prev => { currentRows = prev; return prev; });

    for (const entry of planData) {
      const { symbol, exchange = 'NSE', buyQty } = entry;
      if (!symbol) continue;
      const qty = String(parseInt(buyQty) || 0);
      const alreadyExists = currentRows.some(r => r.symbol === symbol && r.exchange === exchange)
        || newStocks.some(r => r.symbol === symbol && r.exchange === exchange);
      if (alreadyExists) {
        // Will update qty in the batch below
        newStocks.push({ symbol, exchange, qty, existingOnly: true });
      } else {
        try {
          const price = await fetchStockPrice(symbol, exchange);
          newStocks.push({
            symbol, exchange, qty, existingOnly: false,
            name: price.name || symbol,
            low: price.week_52_low || 0,
            current: price.current_price || 0,
            high: price.week_52_high || 0,
          });
        } catch {
          newStocks.push({
            symbol, exchange, qty, existingOnly: false,
            name: symbol, low: 0, current: 0, high: 0,
          });
        }
      }
    }
    // Single setRows call — update existing + prepend new
    setRows(prev => {
      let updated = [...prev];
      const toAdd = [];
      for (const s of newStocks) {
        const idx = updated.findIndex(r => r.symbol === s.symbol && r.exchange === s.exchange);
        if (idx >= 0) {
          updated[idx] = { ...updated[idx], buyQty: s.qty };
        } else {
          toAdd.push({
            symbol: s.symbol, exchange: s.exchange,
            name: s.name, onHand: 0,
            low: s.low, current: s.current, high: s.high,
            buyQty: s.qty,
          });
        }
      }
      return [...toAdd, ...updated];
    });
  };

  // Upload handler — supports PNG (with embedded data) and JSON
  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isPNG = file.type === 'image/png' || file.name.endsWith('.png');
    if (isPNG) {
      const reader = new FileReader();
      reader.onload = async (evt) => {
        try {
          const planData = extractPlanFromPNG(evt.target.result);
          if (planData) {
            await importPlanData(planData);
          } else {
            console.error('No plan data found in image');
          }
        } catch (err) {
          console.error('Failed to parse plan from image:', err);
        }
      };
      reader.readAsArrayBuffer(file);
    } else {
      const reader = new FileReader();
      reader.onload = async (evt) => {
        try {
          const planData = JSON.parse(evt.target.result);
          await importPlanData(planData);
        } catch (err) {
          console.error('Failed to parse plan file:', err);
        }
      };
      reader.readAsText(file);
    }
    e.target.value = '';
  };

  return (
    <div className="modal-overlay" onClick={onClose} style={{ overflow: 'auto', padding: '24px 0' }}>
      <div
        className="modal"
        style={{ maxWidth: '960px', width: '95vw', maxHeight: '90vh', overflow: 'hidden', margin: 'auto', padding: 0, display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky header: title + upload + search */}
        <div style={{ padding: '24px 28px 0', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <h2 style={{ margin: 0 }}>Buy Planner</h2>
            <div>
              <input
                ref={fileInputRef}
                type="file"
                accept=".json,.png,image/png"
                onChange={handleUpload}
                style={{ display: 'none' }}
              />
              <button className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()}>
                Upload Plan
              </button>
            </div>
          </div>
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
        <div style={{ padding: '16px 28px', borderTop: '1px solid var(--border)', flexShrink: 0, display: 'flex', justifyContent: 'flex-end', gap: '12px', alignItems: 'center' }}>
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          <button
            className="btn btn-primary"
            onClick={handleDownload}
            disabled={generating || rowsWithQty.length === 0}
          >
            {generating ? 'Generating...' : 'Download'}
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
