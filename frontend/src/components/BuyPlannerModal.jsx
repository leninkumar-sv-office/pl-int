import React, { useState, useEffect, useRef, useCallback } from 'react';
import { searchStock, fetchStockPrice, getStockSummary } from '../services/api';
import html2canvas from 'html2canvas';

const STORAGE_KEY = 'buyPlannerData';

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

const loadSaved = () => {
  try { const raw = localStorage.getItem(STORAGE_KEY); if (raw) return JSON.parse(raw); } catch {}
  return [];
};

const savePlan = (rows) => {
  const data = rows
    .filter(r => (parseInt(r.buyQty) || 0) > 0 || (parseInt(r.sellQty) || 0) > 0)
    .map(r => ({ symbol: r.symbol, exchange: r.exchange, buyQty: r.buyQty || '', sellQty: r.sellQty || '' }));
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

// Opens the Trade Planner in a new browser window
export function openTradePlanner() {
  const w = window.open('/?view=trade-planner', 'tradePlanner', 'width=1100,height=750,menubar=no,toolbar=no,location=no,status=no');
  if (w) w.focus();
}

// Full-page Trade Planner component (renders when ?view=trade-planner)
export default function TradePlanner() {
  const [stocks, setStocks] = useState([]);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [fetchingPrice, setFetchingPrice] = useState(null);
  const [generating, setGenerating] = useState(false);
  const captureRef = useRef(null);
  const searchDebounceRef = useRef(null);
  const searchInputRef = useRef(null);
  const fileInputRef = useRef(null);
  const initializedRef = useRef(false);

  // Fetch stock summary on mount
  useEffect(() => {
    document.title = 'Trade Planner';
    getStockSummary().then(data => { setStocks(data); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  // Pre-populate from portfolio stocks + restore saved quantities
  useEffect(() => {
    if (!stocks || stocks.length === 0 || initializedRef.current) return;
    initializedRef.current = true;

    const saved = loadSaved();
    const savedMap = {};
    saved.forEach(s => { savedMap[`${s.symbol}.${s.exchange}`] = s; });

    const held = stocks.filter(s => s.total_held_qty > 0);
    const initial = held.map(s => {
      const key = `${s.symbol}.${s.exchange}`;
      const sv = savedMap[key];
      delete savedMap[key];
      return {
        symbol: s.symbol, exchange: s.exchange, name: s.name,
        onHand: s.total_held_qty,
        low: s.live?.week_52_low || 0, current: s.live?.current_price || 0, high: s.live?.week_52_high || 0,
        buyQty: sv?.buyQty || '', sellQty: sv?.sellQty || '',
      };
    });
    initial.sort((a, b) => a.symbol.localeCompare(b.symbol));

    const remaining = Object.values(savedMap);
    if (remaining.length > 0) {
      const placeholders = remaining.map(s => ({
        symbol: s.symbol, exchange: s.exchange, name: s.symbol,
        onHand: 0, low: 0, current: 0, high: 0,
        buyQty: s.buyQty || '', sellQty: s.sellQty || '',
      }));
      setRows([...placeholders, ...initial]);
      remaining.forEach(async (s) => {
        try {
          const price = await fetchStockPrice(s.symbol, s.exchange);
          setRows(prev => prev.map(r =>
            r.symbol === s.symbol && r.exchange === s.exchange
              ? { ...r, name: price.name || s.symbol, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0 }
              : r
          ));
        } catch {}
      });
    } else {
      setRows(initial);
    }
  }, [stocks]);

  // Persist to localStorage
  useEffect(() => {
    if (initializedRef.current && rows.length > 0) savePlan(rows);
  }, [rows]);

  const filteredRows = searchQuery.trim()
    ? rows.filter(r => {
        const q = searchQuery.trim().toLowerCase();
        return r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q);
      })
    : rows;

  const handleSearchChange = useCallback((e) => {
    const q = e.target.value;
    setSearchQuery(q);
    if (searchDebounceRef.current) clearTimeout(searchDebounceRef.current);
    if (!q.trim() || q.trim().length < 2) { setSearchResults([]); return; }
    searchDebounceRef.current = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await searchStock(q.trim());
        const existingSymbols = new Set(rows.map(r => r.symbol));
        setSearchResults(results.filter(r => !existingSymbols.has(r.symbol)));
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 400);
  }, [rows]);

  const clearSearch = () => { setSearchQuery(''); setSearchResults([]); };

  const handleAddStock = async (result) => {
    setFetchingPrice(result.symbol);
    setSearchQuery(''); setSearchResults([]);
    try {
      const price = await fetchStockPrice(result.symbol, result.exchange);
      setRows(prev => [{ symbol: result.symbol, exchange: result.exchange, name: price.name || result.name,
        onHand: 0, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0,
        buyQty: '', sellQty: '' }, ...prev]);
    } catch {
      setRows(prev => [{ symbol: result.symbol, exchange: result.exchange, name: result.name,
        onHand: 0, low: 0, current: 0, high: 0, buyQty: '', sellQty: '' }, ...prev]);
    } finally { setFetchingPrice(null); }
  };

  const updateQty = (idx, field, value) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const removeRow = (idx) => {
    setRows(prev => prev.filter((_, i) => i !== idx));
  };

  const clearAllQty = () => {
    setRows(prev => prev.map(r => ({ ...r, buyQty: '', sellQty: '' })));
    localStorage.removeItem(STORAGE_KEY);
  };

  const buyTotal = rows.reduce((sum, r) => sum + (parseInt(r.buyQty) || 0) * r.current, 0);
  const sellTotal = rows.reduce((sum, r) => sum + (parseInt(r.sellQty) || 0) * r.current, 0);
  const rowsWithQty = rows.filter(r => (parseInt(r.buyQty) || 0) > 0 || (parseInt(r.sellQty) || 0) > 0);
  const hasAnyQty = rowsWithQty.length > 0;

  // ── PNG tEXt chunk helpers ──
  const PLAN_KEY = 'BuyPlan';
  const crc32 = (bytes) => {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) { crc ^= bytes[i]; for (let j = 0; j < 8; j++) crc = (crc >>> 1) ^ (crc & 1 ? 0xEDB88320 : 0); }
    return (crc ^ 0xFFFFFFFF) >>> 0;
  };
  const insertPNGTextChunk = (pngBytes, key, value) => {
    const data = new TextEncoder().encode(key + '\0' + value);
    const chunk = new Uint8Array(12 + data.length);
    const view = new DataView(chunk.buffer);
    view.setUint32(0, data.length);
    chunk[4] = 0x74; chunk[5] = 0x45; chunk[6] = 0x58; chunk[7] = 0x74;
    chunk.set(data, 8);
    view.setUint32(8 + data.length, crc32(chunk.slice(4, 8 + data.length)));
    const result = new Uint8Array(pngBytes.length + chunk.length);
    result.set(pngBytes.slice(0, pngBytes.length - 12), 0);
    result.set(chunk, pngBytes.length - 12);
    result.set(pngBytes.slice(pngBytes.length - 12), pngBytes.length - 12 + chunk.length);
    return result;
  };
  const readPNGTextChunk = (bytes, key) => {
    let offset = 8;
    while (offset < bytes.length) {
      const view = new DataView(bytes.buffer, bytes.byteOffset + offset);
      const len = view.getUint32(0);
      const type = new TextDecoder().decode(bytes.slice(offset + 4, offset + 8));
      if (type === 'tEXt') {
        const chunkData = bytes.slice(offset + 8, offset + 8 + len);
        const nullIdx = chunkData.indexOf(0);
        if (nullIdx >= 0) {
          const chunkKey = new TextDecoder().decode(chunkData.slice(0, nullIdx));
          if (chunkKey === key) return new TextDecoder().decode(chunkData.slice(nullIdx + 1));
        }
      }
      if (type === 'IEND') break;
      offset += 12 + len;
    }
    return null;
  };

  const handleDownload = async () => {
    if (!hasAnyQty) return;
    setGenerating(true);
    try {
      await new Promise(r => setTimeout(r, 100));
      const canvas = await html2canvas(captureRef.current, { backgroundColor: '#1a1a2e', scale: 2 });
      const dateStr = new Date().toISOString().split('T')[0];
      const planData = rowsWithQty.map(r => ({
        symbol: r.symbol, exchange: r.exchange,
        buyQty: parseInt(r.buyQty) || 0, sellQty: parseInt(r.sellQty) || 0,
      }));
      const pngBlob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      const pngBuf = new Uint8Array(await pngBlob.arrayBuffer());
      const withData = insertPNGTextChunk(pngBuf, PLAN_KEY, JSON.stringify(planData));
      const finalBlob = new Blob([withData], { type: 'image/png' });
      const link = document.createElement('a');
      link.download = `trade-plan-${dateStr}.png`;
      link.href = URL.createObjectURL(finalBlob);
      link.click();
      URL.revokeObjectURL(link.href);
    } catch (err) { console.error('Image generation failed:', err); }
    finally { setGenerating(false); }
  };

  const extractPlanFromPNG = (arrayBuffer) => {
    const bytes = new Uint8Array(arrayBuffer);
    const json = readPNGTextChunk(bytes, PLAN_KEY);
    if (!json) return null;
    return JSON.parse(json);
  };

  const importPlanData = async (planData) => {
    if (!Array.isArray(planData) || planData.length === 0) return;
    let currentRows = [];
    setRows(prev => { currentRows = prev; return prev; });
    const newStocks = [];
    for (const entry of planData) {
      const { symbol, exchange = 'NSE', buyQty, sellQty } = entry;
      if (!symbol) continue;
      const bq = String(parseInt(buyQty) || 0);
      const sq = String(parseInt(sellQty) || 0);
      const exists = currentRows.some(r => r.symbol === symbol && r.exchange === exchange)
        || newStocks.some(r => r.symbol === symbol && r.exchange === exchange);
      if (exists) {
        newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: true });
      } else {
        try {
          const price = await fetchStockPrice(symbol, exchange);
          newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: false,
            name: price.name || symbol, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0 });
        } catch {
          newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: false,
            name: symbol, low: 0, current: 0, high: 0 });
        }
      }
    }
    setRows(prev => {
      let updated = [...prev];
      const toAdd = [];
      for (const s of newStocks) {
        const idx = updated.findIndex(r => r.symbol === s.symbol && r.exchange === s.exchange);
        if (idx >= 0) { updated[idx] = { ...updated[idx], buyQty: s.buyQty, sellQty: s.sellQty }; }
        else { toAdd.push({ symbol: s.symbol, exchange: s.exchange, name: s.name, onHand: 0,
          low: s.low, current: s.current, high: s.high, buyQty: s.buyQty, sellQty: s.sellQty }); }
      }
      return [...toAdd, ...updated];
    });
  };

  const handleUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const isPNG = file.type === 'image/png' || file.name.endsWith('.png');
    if (isPNG) {
      const reader = new FileReader();
      reader.onload = async (evt) => {
        try { const d = extractPlanFromPNG(evt.target.result); if (d) await importPlanData(d); }
        catch (err) { console.error('Failed to parse plan from image:', err); }
      };
      reader.readAsArrayBuffer(file);
    } else {
      const reader = new FileReader();
      reader.onload = async (evt) => {
        try { await importPlanData(JSON.parse(evt.target.result)); }
        catch (err) { console.error('Failed to parse plan file:', err); }
      };
      reader.readAsText(file);
    }
    e.target.value = '';
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading stocks...</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '16px 24px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h2 style={{ margin: 0, fontSize: '20px' }}>Trade Planner</h2>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input ref={fileInputRef} type="file" accept=".json,.png,image/png" onChange={handleUpload} style={{ display: 'none' }} />
            <button className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()}>Upload Plan</button>
            {hasAnyQty && (
              <button className="btn btn-ghost btn-sm" onClick={clearAllQty} style={{ color: 'var(--red)' }}>Clear All</button>
            )}
          </div>
        </div>
        {/* Search */}
        <div style={{ position: 'relative', marginBottom: '12px' }}>
          <input ref={searchInputRef} type="text" value={searchQuery} onChange={handleSearchChange}
            placeholder="Search / filter stocks or add new..."
            style={{ width: '100%', padding: '8px 32px 8px 12px', background: 'var(--surface)', border: '1px solid var(--border)',
              borderRadius: '6px', color: 'var(--text)', fontSize: '13px', boxSizing: 'border-box' }}
          />
          {searchQuery && (
            <button onClick={clearSearch}
              style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', background: 'none',
                border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px', padding: '0 4px', lineHeight: 1 }}
              title="Clear search">×</button>
          )}
        </div>
        {(searchResults.length > 0 || searching || fetchingPrice) && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '6px', marginBottom: '12px', maxHeight: '160px', overflowY: 'auto' }}>
            {fetchingPrice && <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-muted)' }}>Fetching price for {fetchingPrice}...</div>}
            {searching && !fetchingPrice && <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--text-muted)' }}>Searching...</div>}
            {searchResults.map((r) => (
              <div key={`${r.symbol}-${r.exchange}`} onClick={() => handleAddStock(r)}
                style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: '13px' }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
                <span style={{ fontWeight: 600 }}>{r.symbol}</span>
                <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>{r.name} · {r.exchange}</span>
                <span style={{ float: 'right', fontSize: '11px', color: 'var(--green)' }}>+ Add</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Table */}
      <div style={{ overflow: 'auto', flex: 1, padding: '0 24px', borderTop: '1px solid var(--border)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
              <th style={thStyle}>Stock</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>On Hand</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>52W Low</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>CMP</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>52W High</th>
              <th style={{ ...thStyle, textAlign: 'right', width: '80px' }}>Buy Qty</th>
              <th style={{ ...thStyle, textAlign: 'right', width: '80px' }}>Sell Qty</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Est. Amount</th>
              <th style={{ ...thStyle, width: '28px' }}></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const idx = rows.findIndex(r => r.symbol === row.symbol && r.exchange === row.exchange);
              const bq = parseInt(row.buyQty) || 0;
              const sq = parseInt(row.sellQty) || 0;
              const hasQty = bq > 0 || sq > 0;
              return (
                <tr key={`${row.symbol}-${row.exchange}`}
                  style={{ borderBottom: '1px solid var(--border)', opacity: hasQty ? 1 : 0.5, transition: 'opacity 0.2s' }}>
                  <td style={tdStyle}>
                    <div style={{ fontWeight: 600 }}>{row.symbol}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{row.name} · {row.exchange}</div>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.onHand || '--'}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.low ? formatINR(row.low) : '--'}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{row.current ? formatINR(row.current) : '--'}</td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{row.high ? formatINR(row.high) : '--'}</td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    <input type="number" min="0" value={row.buyQty} onChange={(e) => updateQty(idx, 'buyQty', e.target.value)} placeholder="0" style={qtyInputStyle} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }}>
                    <input type="number" min="0" value={row.sellQty} onChange={(e) => updateQty(idx, 'sellQty', e.target.value)} placeholder="0" style={qtyInputStyle} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontWeight: hasQty ? 600 : 400, fontVariantNumeric: 'tabular-nums' }}>
                    {hasQty ? (
                      <>
                        {bq > 0 && <div style={{ color: 'var(--green)' }}>+{formatINR(bq * row.current)}</div>}
                        {sq > 0 && <div style={{ color: 'var(--red)' }}>-{formatINR(sq * row.current)}</div>}
                      </>
                    ) : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }}>
                    {row.onHand === 0 && (
                      <button onClick={() => removeRow(idx)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px', padding: '2px' }}
                        title="Remove">x</button>
                    )}
                  </td>
                </tr>
              );
            })}
            {filteredRows.length === 0 && searchQuery.trim() && (
              <tr><td colSpan={9} style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                No matching stocks — select from dropdown to add new</td></tr>
            )}
            {filteredRows.length > 0 && (
              <tr style={{ borderTop: '2px solid var(--border)' }}>
                <td colSpan={7} style={{ ...tdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>Grand Total</td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {buyTotal > 0 && <div style={{ color: 'var(--green)' }}>+{formatINR(buyTotal)}</div>}
                  {sellTotal > 0 && <div style={{ color: 'var(--red)' }}>-{formatINR(sellTotal)}</div>}
                  {!buyTotal && !sellTotal && <span style={{ color: 'var(--text-muted)' }}>--</span>}
                </td>
                <td></td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={{ padding: '12px 24px', borderTop: '1px solid var(--border)', flexShrink: 0, display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
        <button className="btn btn-primary btn-sm" onClick={handleDownload} disabled={generating || !hasAnyQty}>
          {generating ? 'Generating...' : 'Download Image'}
        </button>
      </div>

      {/* Hidden capture div */}
      {hasAnyQty && (
        <div style={{ position: 'absolute', left: '-9999px', top: 0 }}>
          <div ref={captureRef} style={{ background: '#1a1a2e', color: '#e0e0e0', padding: '24px 28px',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', width: '920px' }}>
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '18px', fontWeight: 700, color: '#ffffff' }}>Trade Plan — {todayStr()}</div>
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #333355' }}>
                  <th style={capThStyle}>Stock</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>On Hand</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>52W Low</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>CMP</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>52W High</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>Buy</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>Sell</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {rowsWithQty.map((row) => {
                  const bq = parseInt(row.buyQty) || 0;
                  const sq = parseInt(row.sellQty) || 0;
                  return (
                    <tr key={row.symbol} style={{ borderBottom: '1px solid #2a2a45' }}>
                      <td style={capTdStyle}>
                        <span style={{ fontWeight: 600 }}>{row.symbol}</span>
                        <span style={{ color: '#888', marginLeft: '6px', fontSize: '11px' }}>{row.exchange}</span>
                      </td>
                      <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.onHand || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.low ? formatINR(row.low) : '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(row.current)}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right' }}>{row.high ? formatINR(row.high) : '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600, color: bq ? '#4ade80' : '#888' }}>{bq || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600, color: sq ? '#f87171' : '#888' }}>{sq || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>
                        {bq > 0 && <div style={{ color: '#4ade80' }}>+{formatINR(bq * row.current)}</div>}
                        {sq > 0 && <div style={{ color: '#f87171' }}>-{formatINR(sq * row.current)}</div>}
                      </td>
                    </tr>
                  );
                })}
                <tr style={{ borderTop: '2px solid #333355' }}>
                  <td colSpan={7} style={{ ...capTdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>Grand Total</td>
                  <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, fontSize: '14px' }}>
                    {buyTotal > 0 && <div style={{ color: '#4ade80' }}>+{formatINR(buyTotal)}</div>}
                    {sellTotal > 0 && <div style={{ color: '#f87171' }}>-{formatINR(sellTotal)}</div>}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const thStyle = { padding: '8px 6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' };
const tdStyle = { padding: '8px 6px' };
const qtyInputStyle = { width: '70px', padding: '4px 8px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)', textAlign: 'right', fontSize: '13px' };
const capThStyle = { padding: '8px 6px', fontSize: '11px', fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px', textAlign: 'left' };
const capTdStyle = { padding: '8px 6px', fontVariantNumeric: 'tabular-nums' };
