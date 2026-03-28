import React, { useState, useEffect, useRef, useCallback } from 'react';
import { searchStock, fetchStockPrice, getStockSummary, getStockHistory } from '../services/api';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import html2canvas from 'html2canvas';

const STORAGE_KEY = 'buyPlannerData';

const formatINR = (num) => {
  if (num === null || num === undefined || isNaN(num)) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const fmtAmt = (v) => {
  if (!v || Math.abs(v) < 0.01) return '';
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  if (abs >= 10000000) return `${sign}₹${(abs / 10000000).toFixed(1)}Cr`;
  if (abs >= 100000) return `${sign}₹${(abs / 100000).toFixed(1)}L`;
  if (abs >= 1000) return `${sign}₹${(abs / 1000).toFixed(1)}K`;
  if (abs >= 100) return `${sign}₹${Math.round(abs)}`;
  if (abs >= 10) return `${sign}₹${abs.toFixed(1)}`;
  return `${sign}₹${abs.toFixed(2)}`;
};

const calcPa = (pnl, invested, earliestDate) => {
  if (!earliestDate || invested <= 0 || pnl === 0) return null;
  const days = Math.floor((Date.now() - new Date(earliestDate + 'T00:00:00').getTime()) / 86400000);
  if (days <= 0) return null;
  return (Math.pow(1 + pnl / invested, 365 / days) - 1) * 100;
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
    .map(r => ({ symbol: r.symbol, exchange: r.exchange, buyQty: r.buyQty || '', sellQty: r.sellQty || '', ltSellQty: r.ltSellQty || '', stSellQty: r.stSellQty || '' }));
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
  const [searchHighlight, setSearchHighlight] = useState(-1);
  const [searching, setSearching] = useState(false);
  const [fetchingPrice, setFetchingPrice] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [sortField, setSortField] = useState('signal');
  const [sortDir, setSortDir] = useState('desc');
  const [expandedSymbol, setExpandedSymbol] = useState(null); // "SYMBOL.EXCHANGE" or null
  const [chartPeriod, setChartPeriod] = useState('1y');
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
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

    // Show ALL stocks (held + watchlist), not just held
    const initial = stocks.map(s => {
      const key = `${s.symbol}.${s.exchange}`;
      const sv = savedMap[key];
      delete savedMap[key];
      const ltQty = (s.ltcg_profitable_qty || 0) + (s.ltcg_loss_qty || 0);
      const stQty = (s.stcg_profitable_qty || 0) + (s.stcg_loss_qty || 0);
      return {
        symbol: s.symbol, exchange: s.exchange, name: s.name,
        onHand: s.total_held_qty || 0, avgBuy: s.avg_buy_price || 0,
        totalInvested: s.total_invested || 0, ltcgInvested: s.ltcg_invested || 0, stcgInvested: s.stcg_invested || 0,
        ltcgEarliestDate: s.ltcg_earliest_date || '', stcgEarliestDate: s.stcg_earliest_date || '',
        lastTxDate: s.last_tx_date || '', lastTxType: s.last_tx_type || '',
        low: s.live?.week_52_low || 0, current: s.live?.current_price || 0, high: s.live?.week_52_high || 0,
        sma200: s.live?.sma_200 || 0, daysBelowSma: s.live?.days_below_sma || 0, rsi: s.live?.rsi, signal: s.live?.signal,
        dayChange: s.live?.day_change || 0, dayChangePct: s.live?.day_change_pct || 0,
        weekChangePct: s.live?.week_change_pct || 0, monthChangePct: s.live?.month_change_pct || 0,
        buyQty: sv?.buyQty || '', sellQty: sv?.sellQty || '', ltSellQty: sv?.ltSellQty || '', stSellQty: sv?.stSellQty || '',
        ltAvail: ltQty, stAvail: stQty,
      };
    });
    initial.sort((a, b) => a.symbol.localeCompare(b.symbol));

    // Add any saved stocks that aren't in the portfolio at all
    const allSymbols = new Set(initial.map(r => r.symbol));
    const remaining = Object.values(savedMap).filter(s => !allSymbols.has(s.symbol));
    if (remaining.length > 0) {
      const placeholders = remaining.map(s => ({
        symbol: s.symbol, exchange: s.exchange, name: s.symbol,
        onHand: 0, low: 0, current: 0, high: 0,
        dayChange: 0, dayChangePct: 0, weekChangePct: 0, monthChangePct: 0,
        buyQty: s.buyQty || '', sellQty: s.sellQty || '', ltSellQty: s.ltSellQty || '', stSellQty: s.stSellQty || '',
        ltAvail: 0, stAvail: 0,
      }));
      setRows([...placeholders, ...initial]);
      remaining.forEach(async (s) => {
        try {
          const price = await fetchStockPrice(s.symbol, s.exchange);
          setRows(prev => prev.map(r =>
            r.symbol === s.symbol && r.exchange === s.exchange
              ? { ...r, name: price.name || s.symbol, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0,
                  sma200: price.sma_200 || 0, daysBelowSma: price.days_below_sma || 0, rsi: price.rsi, signal: price.signal,
                  dayChange: price.day_change || 0, dayChangePct: price.day_change_pct || 0,
                  weekChangePct: price.week_change_pct || 0, monthChangePct: price.month_change_pct || 0 }
              : r
          ));
        } catch {}
      });
    } else {
      setRows(initial);
    }
  }, [stocks]);

  // Update SMA/RSI from stocks data when available (may arrive after initial load)
  useEffect(() => {
    if (!stocks || stocks.length === 0 || rows.length === 0) return;
    const liveMap = {};
    stocks.forEach(s => { if (s.live) liveMap[`${s.symbol}.${s.exchange}`] = s.live; });
    setRows(prev => prev.map(r => {
      const live = liveMap[`${r.symbol}.${r.exchange}`];
      if (!live || (r.sma200 && r.rsi != null)) return r; // already has data
      return { ...r, sma200: live.sma_200 || 0, daysBelowSma: live.days_below_sma || 0, rsi: live.rsi, signal: live.signal };
    }));
  }, [stocks]);

  // Persist to localStorage
  useEffect(() => {
    if (initializedRef.current && rows.length > 0) savePlan(rows);
  }, [rows]);

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span style={{ opacity: 0.3, marginLeft: '4px' }}>↕</span>;
    return <span style={{ marginLeft: '4px' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  const sortedRows = [...rows].sort((a, b) => {
    // Rows with qty always first
    const aHas = (parseInt(a.buyQty) || 0) > 0 || (parseInt(a.sellQty) || 0) > 0 ? 0 : 1;
    const bHas = (parseInt(b.buyQty) || 0) > 0 || (parseInt(b.sellQty) || 0) > 0 ? 0 : 1;
    if (aHas !== bHas) return aHas - bHas;

    let av, bv;
    switch (sortField) {
      case 'symbol': av = a.symbol; bv = b.symbol; break;
      case 'onHand': av = a.onHand || 0; bv = b.onHand || 0; break;
      case 'week_52_low': {
        av = a.current > 0 && a.low > 0 ? ((a.current - a.low) / a.low * 100) : 9999;
        bv = b.current > 0 && b.low > 0 ? ((b.current - b.low) / b.low * 100) : 9999;
        break;
      }
      case 'day_change_pct': av = a.dayChangePct || 0; bv = b.dayChangePct || 0; break;
      case 'week_52_high': {
        av = a.current > 0 && a.high > 0 ? ((a.high - a.current) / a.high * 100) : 9999;
        bv = b.current > 0 && b.high > 0 ? ((b.high - b.current) / b.high * 100) : 9999;
        break;
      }
      case 'signal': {
        const base = { strong_bull: 400, weak_bull: 200, weak_bear: -200, strong_bear: -400 };
        const aPct = a.sma200 > 0 && a.current > 0 ? ((a.current - a.sma200) / a.sma200 * 100) : -9999;
        const bPct = b.sma200 > 0 && b.current > 0 ? ((b.current - b.sma200) / b.sma200 * 100) : -9999;
        av = (base[a.signal] ?? -500) + aPct;
        bv = (base[b.signal] ?? -500) + bPct;
        break;
      }
      case 'rsi': av = a.rsi ?? -1; bv = b.rsi ?? -1; break;
      default: av = a.symbol; bv = b.symbol;
    }
    if (typeof av === 'string') {
      const cmp = av.localeCompare(bv);
      return sortDir === 'asc' ? cmp : -cmp;
    }
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  const filteredRows = searchQuery.trim()
    ? sortedRows.filter(r => {
        const q = searchQuery.trim().toLowerCase();
        return r.symbol.toLowerCase().includes(q) || r.name.toLowerCase().includes(q);
      })
    : sortedRows;

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

  const clearSearch = () => { setSearchQuery(''); setSearchResults([]); setSearchHighlight(-1); };

  useEffect(() => { setSearchHighlight(-1); }, [searchResults]);

  const handleAddStock = async (result) => {
    setFetchingPrice(result.symbol);
    setSearchQuery(''); setSearchResults([]);
    try {
      const price = await fetchStockPrice(result.symbol, result.exchange);
      setRows(prev => [{ symbol: result.symbol, exchange: result.exchange, name: price.name || result.name,
        onHand: 0, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0,
        sma200: price.sma_200 || 0, daysBelowSma: price.days_below_sma || 0, rsi: price.rsi, signal: price.signal,
        dayChange: price.day_change || 0, dayChangePct: price.day_change_pct || 0,
        weekChangePct: price.week_change_pct || 0, monthChangePct: price.month_change_pct || 0,
        buyQty: '', sellQty: '', ltSellQty: '', stSellQty: '', ltAvail: 0, stAvail: 0 }, ...prev]);
    } catch {
      setRows(prev => [{ symbol: result.symbol, exchange: result.exchange, name: result.name,
        onHand: 0, low: 0, current: 0, high: 0, dayChange: 0, dayChangePct: 0, weekChangePct: 0, monthChangePct: 0,
        buyQty: '', sellQty: '', ltSellQty: '', stSellQty: '', ltAvail: 0, stAvail: 0 }, ...prev]);
    } finally { setFetchingPrice(null); }
  };

  const updateQty = (idx, field, value) => {
    setRows(prev => prev.map((r, i) => i === idx ? { ...r, [field]: value } : r));
  };

  const updateSellQty = (idx, value) => {
    setRows(prev => prev.map((r, i) => {
      if (i !== idx) return r;
      const total = parseInt(value) || 0;
      const lt = Math.min(total, r.ltAvail || 0);
      const st = Math.min(total - lt, r.stAvail || 0);
      return { ...r, sellQty: value, ltSellQty: lt > 0 ? String(lt) : '', stSellQty: st > 0 ? String(st) : '' };
    }));
  };

  const removeRow = (idx) => {
    setRows(prev => prev.filter((_, i) => i !== idx));
  };

  const clearAllQty = () => {
    setRows(prev => prev.map(r => ({ ...r, buyQty: '', sellQty: '', ltSellQty: '', stSellQty: '' })));
    localStorage.removeItem(STORAGE_KEY);
  };

  const CHART_PERIODS = ['1D', '5D', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX'];

  const fetchChart = useCallback(async (symbol, exchange, period) => {
    setChartLoading(true);
    setChartData([]);
    try {
      const data = await getStockHistory(symbol, exchange, period.toLowerCase());
      setChartData(data || []);
    } catch { setChartData([]); }
    finally { setChartLoading(false); }
  }, []);

  const handleRowClick = useCallback((row) => {
    const key = `${row.symbol}.${row.exchange}`;
    if (expandedSymbol === key) {
      setExpandedSymbol(null);
    } else {
      setExpandedSymbol(key);
      setChartPeriod('1y');
      fetchChart(row.symbol, row.exchange, '1y');
    }
  }, [expandedSymbol, fetchChart]);

  const handlePeriodChange = useCallback((period, row) => {
    setChartPeriod(period.toLowerCase());
    fetchChart(row.symbol, row.exchange, period);
  }, [fetchChart]);

  const formatChartDate = (dateStr, period) => {
    const d = new Date(dateStr);
    if (period === '1d' || period === '5d') {
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    }
    if (period === '1m') return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' });
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
      const { symbol, exchange = 'NSE', buyQty, sellQty, ltSellQty, stSellQty } = entry;
      if (!symbol) continue;
      const bq = String(parseInt(buyQty) || 0);
      const sq = String(parseInt(sellQty) || (parseInt(ltSellQty) || 0) + (parseInt(stSellQty) || 0) || 0);
      const exists = currentRows.some(r => r.symbol === symbol && r.exchange === exchange)
        || newStocks.some(r => r.symbol === symbol && r.exchange === exchange);
      if (exists) {
        newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: true });
      } else {
        try {
          const price = await fetchStockPrice(symbol, exchange);
          newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: false,
            name: price.name || symbol, low: price.week_52_low || 0, current: price.current_price || 0, high: price.week_52_high || 0,
            sma200: price.sma_200 || 0, daysBelowSma: price.days_below_sma || 0, rsi: price.rsi, signal: price.signal,
            dayChange: price.day_change || 0, dayChangePct: price.day_change_pct || 0,
            weekChangePct: price.week_change_pct || 0, monthChangePct: price.month_change_pct || 0 });
        } catch {
          newStocks.push({ symbol, exchange, buyQty: bq, sellQty: sq, existingOnly: false,
            name: symbol, low: 0, current: 0, high: 0, dayChange: 0, dayChangePct: 0, weekChangePct: 0, monthChangePct: 0 });
        }
      }
    }
    setRows(prev => {
      let updated = [...prev];
      const toAdd = [];
      for (const s of newStocks) {
        const idx = updated.findIndex(r => r.symbol === s.symbol && r.exchange === s.exchange);
        if (idx >= 0) {
          const r = updated[idx];
          const total = parseInt(s.sellQty) || 0;
          const lt = Math.min(total, r.ltAvail || 0);
          const st = Math.min(total - lt, r.stAvail || 0);
          updated[idx] = { ...r, buyQty: s.buyQty, sellQty: s.sellQty, ltSellQty: lt > 0 ? String(lt) : '', stSellQty: st > 0 ? String(st) : '' };
        } else {
          toAdd.push({ symbol: s.symbol, exchange: s.exchange, name: s.name, onHand: 0,
            low: s.low, current: s.current, high: s.high,
            dayChange: s.dayChange || 0, dayChangePct: s.dayChangePct || 0,
            weekChangePct: s.weekChangePct || 0, monthChangePct: s.monthChangePct || 0,
            buyQty: s.buyQty, sellQty: s.sellQty, ltSellQty: '', stSellQty: '', ltAvail: 0, stAvail: 0 });
        }
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
            onKeyDown={e => {
              if (e.key === 'Escape') { e.stopPropagation(); clearSearch(); }
              else if (e.key === 'ArrowDown' && searchResults.length > 0) { e.preventDefault(); setSearchHighlight(prev => (prev + 1) % searchResults.length); }
              else if (e.key === 'ArrowUp' && searchResults.length > 0) { e.preventDefault(); setSearchHighlight(prev => (prev - 1 + searchResults.length) % searchResults.length); }
              else if (e.key === 'Enter' && searchHighlight >= 0 && searchResults[searchHighlight]) { e.preventDefault(); handleAddStock(searchResults[searchHighlight]); }
            }}
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
            {searchResults.map((r, i) => (
              <div key={`${r.symbol}-${r.exchange}`} onClick={() => handleAddStock(r)}
                onMouseEnter={() => setSearchHighlight(i)}
                style={{ padding: '8px 12px', cursor: 'pointer', borderBottom: '1px solid var(--border)', fontSize: '13px',
                  background: i === searchHighlight ? 'rgba(59,130,246,0.15)' : 'transparent' }}>
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
              <th style={{ ...thStyle, cursor: 'pointer' }} onClick={() => handleSort('symbol')}>Stock<SortIcon field="symbol" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('onHand')}>On Hand<SortIcon field="onHand" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('week_52_low')}>52W Low<SortIcon field="week_52_low" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('day_change_pct')}>CMP<SortIcon field="day_change_pct" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('week_52_high')}>52W High<SortIcon field="week_52_high" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('signal')} title="Signal (SMA-based trend): Strong Bull, Weak Bull, Weak Bear, Strong Bear">Signal<SortIcon field="signal" /></th>
              <th style={{ ...thStyle, textAlign: 'right', cursor: 'pointer' }} onClick={() => handleSort('rsi')} title="RSI (14-day): <30 Oversold, 30-70 Neutral, >70 Overbought">RSI<SortIcon field="rsi" /></th>
              <th style={{ ...thStyle, textAlign: 'right', width: '80px' }}>Buy Qty</th>
              <th style={{ ...thStyle, textAlign: 'right', width: '80px' }}>Sell Qty</th>
              <th style={{ ...thStyle, textAlign: 'right', width: '60px' }}>LT</th>
              <th style={{ ...thStyle, textAlign: 'right', width: '60px' }}>ST</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Est. Amount</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>LT P&L</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>ST P&L</th>
              <th style={{ ...thStyle, textAlign: 'right' }}>Total P&L</th>
              <th style={{ ...thStyle, width: '28px' }}></th>
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row) => {
              const idx = rows.findIndex(r => r.symbol === row.symbol && r.exchange === row.exchange);
              const bq = parseInt(row.buyQty) || 0;
              const ltSq = parseInt(row.ltSellQty) || 0;
              const stSq = parseInt(row.stSellQty) || 0;
              const totalSq = ltSq + stSq;
              const hasQty = bq > 0 || totalSq > 0;
              const rowKey = `${row.symbol}.${row.exchange}`;
              const isExpanded = expandedSymbol === rowKey;
              const chartUp = chartData.length >= 2 && chartData[chartData.length - 1].close >= chartData[0].close;
              const chartColor = chartUp ? '#00d26a' : '#ff4757';
              const ltPl = ltSq > 0 && row.avgBuy > 0 ? (row.current - row.avgBuy) * ltSq : null;
              const stPl = stSq > 0 && row.avgBuy > 0 ? (row.current - row.avgBuy) * stSq : null;
              const totalPl = (ltPl || 0) + (stPl || 0);
              const hasSellPl = ltPl !== null || stPl !== null;
              const ltPa = ltPl !== null ? calcPa(ltPl, row.avgBuy * ltSq, row.ltcgEarliestDate) : null;
              const stPa = stPl !== null ? calcPa(stPl, row.avgBuy * stSq, row.stcgEarliestDate) : null;
              const earliestDate = [row.ltcgEarliestDate, row.stcgEarliestDate].filter(Boolean).sort()[0] || '';
              const totalPa = hasSellPl ? calcPa(totalPl, row.avgBuy * totalSq, earliestDate) : null;
              return (
                <React.Fragment key={`${row.symbol}-${row.exchange}`}>
                <tr
                  onClick={() => handleRowClick(row)}
                  style={{ borderBottom: isExpanded ? 'none' : '1px solid var(--border)', background: hasQty ? 'rgba(34,197,94,0.08)' : 'transparent', cursor: 'pointer' }}>
                  <td style={tdStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)', transition: 'transform 0.2s', transform: isExpanded ? 'rotate(90deg)' : 'none' }}>&#9654;</span>
                      <div>
                        <div style={{ fontWeight: 600 }}>{row.symbol}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-dim, #aaa)' }}>{row.name} · {row.exchange}</div>
                        {row.lastTxDate && <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Last {row.lastTxType?.toLowerCase() || 'tx'}: {(() => { const d = new Date(row.lastTxDate + 'T00:00:00'); return isNaN(d) ? row.lastTxDate : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' }); })()}</div>}
                      </div>
                    </div>
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.onHand ? (
                      <div>
                        <div style={{ fontWeight: 600 }}>{row.onHand}</div>
                        {row.totalInvested > 0 && <div style={{ fontWeight: 600, color: '#4da6ff' }}>{fmtAmt(row.totalInvested)}</div>}
                      </div>
                    ) : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.low ? (() => {
                      const nearLow = row.current > 0 && row.current <= row.low * 1.05;
                      const pctFromLow = row.current > 0 && row.low > 0 ? ((row.current - row.low) / row.low * 100) : 0;
                      const delta = row.current - row.low;
                      return (
                        <div>
                          <div style={{ color: nearLow ? 'var(--red)' : 'var(--text)', fontWeight: nearLow ? 600 : 400 }}>
                            {formatINR(row.low)}
                          </div>
                          {row.current > 0 && (
                            <div style={{ fontSize: '10px', color: delta >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              {delta >= 0 ? '+' : ''}{pctFromLow.toFixed(2)}%, {fmtAmt(delta) || '+₹0'}
                            </div>
                          )}
                        </div>
                      );
                    })() : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.current ? (
                      <div>
                        <div style={{ fontWeight: 600, color: row.onHand > 0 && row.avgBuy > 0 ? (row.current >= row.avgBuy ? 'var(--green)' : 'var(--red)') : 'var(--text)' }}>
                          {formatINR(row.current)}
                        </div>
                        {(() => {
                          const pct = row.dayChangePct || 0;
                          const amt = fmtAmt(row.dayChange || 0) || '+₹0';
                          return (
                            <div style={{ fontSize: '10px', color: pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              1D: {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%, {amt}
                            </div>
                          );
                        })()}
                        {row.weekChangePct !== 0 && (() => {
                          const amt = fmtAmt(row.current * row.weekChangePct / (100 + row.weekChangePct));
                          return (
                            <div style={{ fontSize: '10px', color: row.weekChangePct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              7D: {row.weekChangePct >= 0 ? '+' : ''}{row.weekChangePct.toFixed(2)}%{amt ? `, ${amt}` : ''}
                            </div>
                          );
                        })()}
                        {row.monthChangePct !== 0 && (() => {
                          const amt = fmtAmt(row.current * row.monthChangePct / (100 + row.monthChangePct));
                          return (
                            <div style={{ fontSize: '10px', color: row.monthChangePct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              1M: {row.monthChangePct >= 0 ? '+' : ''}{row.monthChangePct.toFixed(2)}%{amt ? `, ${amt}` : ''}
                            </div>
                          );
                        })()}
                      </div>
                    ) : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.high ? (() => {
                      const nearHigh = row.current > 0 && row.current >= row.high * 0.95;
                      const pctFromHigh = row.current > 0 && row.high > 0 ? ((row.high - row.current) / row.high * 100) : 0;
                      const delta = row.current - row.high;
                      return (
                        <div>
                          <div style={{ color: nearHigh ? 'var(--green)' : 'var(--text)', fontWeight: nearHigh ? 600 : 400 }}>
                            {formatINR(row.high)}
                          </div>
                          {row.current > 0 && (
                            <div style={{ fontSize: '10px', color: delta >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              {delta >= 0 ? '+' : ''}{(-pctFromHigh).toFixed(2)}%, {fmtAmt(delta) || '-₹0'}
                            </div>
                          )}
                        </div>
                      );
                    })() : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {(() => {
                      const sig = row.signal;
                      const sma = row.sma200, cp = row.current;
                      if (!sig) return <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>--</span>;
                      const pct = sma && cp && sma > 0 ? ((cp - sma) / sma * 100) : null;
                      const pctStr = pct != null ? (pct >= 0 ? `+${pct.toFixed(1)}%` : `${pct.toFixed(1)}%`) : '';
                      const cfg = { strong_bull: { icon: '\u{1F7E2}', label: 'Strong Bull', color: 'var(--green)' }, weak_bull: { icon: '\u{1F7E1}', label: 'Weak Bull', color: 'var(--yellow, #f0ad4e)' }, weak_bear: { icon: '\u{1F7E1}', label: 'Weak Bear', color: 'var(--yellow, #f0ad4e)' }, strong_bear: { icon: '\u{1F534}', label: 'Strong Bear', color: 'var(--red)' } };
                      const c = cfg[sig];
                      if (!c) return <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>--</span>;
                      return <div><div style={{ fontSize: '11px', color: c.color, fontWeight: 600 }}>{c.icon} {c.label}</div>{pctStr && <div style={{ fontSize: '10px', color: c.color }}>{pctStr}</div>}</div>;
                    })()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {(() => {
                      const r = row.rsi;
                      if (r == null) return <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>--</span>;
                      const color = r < 30 ? 'var(--red)' : r > 70 ? 'var(--green)' : 'var(--text)';
                      const label = r < 30 ? 'Oversold' : r > 70 ? 'Overbought' : '';
                      return <div><div style={{ fontSize: '12px', color, fontWeight: 600 }}>{r.toFixed(1)}</div>{label && <div style={{ fontSize: '9px', color }}>{label}</div>}</div>;
                    })()}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    <input type="number" min="0" value={row.buyQty} onChange={(e) => updateQty(idx, 'buyQty', e.target.value)} placeholder="0" style={qtyInputStyle} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right' }} onClick={e => e.stopPropagation()}>
                    <input type="number" min="0" max={(row.ltAvail || 0) + (row.stAvail || 0) || undefined} value={row.sellQty} onChange={(e) => updateSellQty(idx, e.target.value)} placeholder="0" style={qtyInputStyle} />
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: '12px' }}>
                    {ltSq > 0 ? (
                      <div>
                        <div style={{ fontWeight: 600 }}>{ltSq}</div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>/{row.ltAvail || 0}</div>
                      </div>
                    ) : row.ltAvail > 0 ? <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>/{row.ltAvail}</span> : ''}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums', fontSize: '12px' }}>
                    {stSq > 0 ? (
                      <div>
                        <div style={{ fontWeight: 600 }}>{stSq}</div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>/{row.stAvail || 0}</div>
                      </div>
                    ) : row.stAvail > 0 ? <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>/{row.stAvail}</span> : ''}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontWeight: hasQty ? 600 : 400, fontVariantNumeric: 'tabular-nums' }}>
                    {hasQty ? (
                      <>
                        {bq > 0 && <div style={{ color: 'var(--red)' }}>-{formatINR(bq * row.current)}</div>}
                        {totalSq > 0 && <div style={{ color: 'var(--green)' }}>+{formatINR(totalSq * row.current)}</div>}
                      </>
                    ) : '--'}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {ltPl !== null ? (
                      <div>
                        <div style={{ fontWeight: 600, color: ltPl >= 0 ? 'var(--green)' : 'var(--red)' }}>{ltPl >= 0 ? '+' : ''}{formatINR(ltPl)}</div>
                        {ltPa !== null && <div style={{ fontSize: '10px', color: ltPl >= 0 ? 'var(--green)' : 'var(--red)', opacity: 0.85 }}>{ltPa >= 0 ? '+' : ''}{ltPa.toFixed(1)}% p.a.</div>}
                      </div>
                    ) : ''}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {stPl !== null ? (
                      <div>
                        <div style={{ fontWeight: 600, color: stPl >= 0 ? 'var(--green)' : 'var(--red)' }}>{stPl >= 0 ? '+' : ''}{formatINR(stPl)}</div>
                        {stPa !== null && <div style={{ fontSize: '10px', color: stPl >= 0 ? 'var(--green)' : 'var(--red)', opacity: 0.85 }}>{stPa >= 0 ? '+' : ''}{stPa.toFixed(1)}% p.a.</div>}
                      </div>
                    ) : ''}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {hasSellPl ? (
                      <div>
                        <div style={{ fontWeight: 600, color: totalPl >= 0 ? 'var(--green)' : 'var(--red)' }}>{totalPl >= 0 ? '+' : ''}{formatINR(totalPl)}</div>
                        {row.avgBuy > 0 && <div style={{ fontSize: '11px', color: totalPl >= 0 ? 'var(--green)' : 'var(--red)', opacity: 0.85 }}>{totalPl >= 0 ? '+' : ''}{((row.current - row.avgBuy) / row.avgBuy * 100).toFixed(1)}%</div>}
                        {totalPa !== null && <div style={{ fontSize: '10px', color: totalPl >= 0 ? 'var(--green)' : 'var(--red)', opacity: 0.85 }}>{totalPa >= 0 ? '+' : ''}{totalPa.toFixed(1)}% p.a.</div>}
                      </div>
                    ) : ''}
                  </td>
                  <td style={{ ...tdStyle, textAlign: 'center' }} onClick={e => e.stopPropagation()}>
                    {row.onHand === 0 && (
                      <button onClick={() => removeRow(idx)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px', padding: '2px' }}
                        title="Remove">x</button>
                    )}
                  </td>
                </tr>
                {isExpanded && (
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    <td colSpan={14} style={{ padding: 0 }}>
                      <div style={{ display: 'flex', background: 'var(--surface)', borderLeft: `3px solid ${chartColor}`, minHeight: '220px' }}>
                        {/* Left: price info */}
                        <div style={{ padding: '16px 20px', minWidth: '180px', display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '8px' }}>
                          <div style={{ fontSize: '24px', fontWeight: 700 }}>{row.current ? formatINR(row.current) : '--'}</div>
                          {row.low > 0 && row.high > 0 && (
                            <div style={{ fontSize: '12px', color: 'var(--text-dim, var(--text-muted))' }}>
                              <div style={{ marginBottom: '4px', fontWeight: 500 }}>52W Range</div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <span style={{ color: 'var(--text)' }}>{formatINR(row.low)}</span>
                                <div style={{ flex: 1, height: '4px', background: 'var(--border)', borderRadius: '2px', position: 'relative', minWidth: '60px' }}>
                                  <div style={{
                                    position: 'absolute', top: '-2px',
                                    left: `${Math.min(100, Math.max(0, ((row.current - row.low) / (row.high - row.low)) * 100))}%`,
                                    width: '8px', height: '8px', borderRadius: '50%', background: 'var(--text)',
                                    transform: 'translateX(-50%)',
                                  }} />
                                </div>
                                <span style={{ color: 'var(--text)' }}>{formatINR(row.high)}</span>
                              </div>
                            </div>
                          )}
                        </div>
                        {/* Right: chart */}
                        <div style={{ flex: 1, padding: '12px 16px 12px 0', display: 'flex', flexDirection: 'column' }}>
                          {/* Period tabs */}
                          <div style={{ display: 'flex', gap: '2px', marginBottom: '8px' }}>
                            {CHART_PERIODS.map(p => (
                              <button key={p} onClick={() => handlePeriodChange(p, row)}
                                style={{
                                  padding: '3px 8px', fontSize: '11px', fontWeight: 600, border: 'none', borderRadius: '4px', cursor: 'pointer',
                                  background: chartPeriod === p.toLowerCase() ? 'var(--text)' : 'transparent',
                                  color: chartPeriod === p.toLowerCase() ? 'var(--bg)' : 'var(--text-muted)',
                                }}>
                                {p}
                              </button>
                            ))}
                          </div>
                          {/* Chart area */}
                          <div style={{ flex: 1, minHeight: '160px' }}>
                            {chartLoading ? (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>Loading chart...</div>
                            ) : chartData.length === 0 ? (
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>No data available</div>
                            ) : (
                              <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                                  <defs>
                                    <linearGradient id={`grad-${rowKey}`} x1="0" y1="0" x2="0" y2="1">
                                      <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                                      <stop offset="100%" stopColor={chartColor} stopOpacity={0.02} />
                                    </linearGradient>
                                  </defs>
                                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                                    tickFormatter={(v) => formatChartDate(v, chartPeriod)}
                                    interval="preserveStartEnd" minTickGap={40} />
                                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 10, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                                    tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(0)} width={45} />
                                  <Tooltip
                                    contentStyle={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '11px' }}
                                    labelFormatter={(v) => {
                                      const d = new Date(v);
                                      return (chartPeriod === '1d' || chartPeriod === '5d')
                                        ? d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                                        : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
                                    }}
                                    formatter={(value, name) => [formatINR(value), name.charAt(0).toUpperCase() + name.slice(1)]}
                                  />
                                  <Area type="monotone" dataKey="close" stroke={chartColor} strokeWidth={1.5} fill={`url(#grad-${rowKey})`} dot={false} />
                                </AreaChart>
                              </ResponsiveContainer>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                </React.Fragment>
              );
            })}
            {filteredRows.length === 0 && searchQuery.trim() && (
              <tr><td colSpan={14} style={{ ...tdStyle, textAlign: 'center', color: 'var(--text-muted)', padding: '20px' }}>
                No matching stocks — select from dropdown to add new</td></tr>
            )}
            {filteredRows.length > 0 && (() => {
              const totalLtPL = rows.reduce((sum, r) => {
                const sq = parseInt(r.ltSellQty) || 0;
                if (sq > 0 && r.avgBuy > 0 && r.current > 0) return sum + (r.current - r.avgBuy) * sq;
                return sum;
              }, 0);
              const totalStPL = rows.reduce((sum, r) => {
                const sq = parseInt(r.stSellQty) || 0;
                if (sq > 0 && r.avgBuy > 0 && r.current > 0) return sum + (r.current - r.avgBuy) * sq;
                return sum;
              }, 0);
              const totalRealizedPL = totalLtPL + totalStPL;
              return (
              <tr style={{ borderTop: '2px solid var(--border)' }}>
                <td colSpan={9} style={{ ...tdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>Grand Total</td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {buyTotal > 0 && <div style={{ color: 'var(--red)' }}>-{formatINR(buyTotal)}</div>}
                  {sellTotal > 0 && <div style={{ color: 'var(--green)' }}>+{formatINR(sellTotal)}</div>}
                  {!buyTotal && !sellTotal && <span style={{ color: 'var(--text-muted)' }}>--</span>}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {totalLtPL !== 0 ? (
                    <div style={{ color: totalLtPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {totalLtPL >= 0 ? '+' : ''}{formatINR(totalLtPL)}
                    </div>
                  ) : ''}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {totalStPL !== 0 ? (
                    <div style={{ color: totalStPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {totalStPL >= 0 ? '+' : ''}{formatINR(totalStPL)}
                    </div>
                  ) : ''}
                </td>
                <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>
                  {totalRealizedPL !== 0 ? (
                    <div style={{ color: totalRealizedPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {totalRealizedPL >= 0 ? '+' : ''}{formatINR(totalRealizedPL)}
                    </div>
                  ) : ''}
                </td>
                <td></td>
              </tr>
              );
            })()}
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
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif', width: '1200px' }}>
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
                  <th style={{ ...capThStyle, textAlign: 'right' }}>LT</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>ST</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>Amount</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>LT P&L</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>ST P&L</th>
                  <th style={{ ...capThStyle, textAlign: 'right' }}>Total P&L</th>
                </tr>
              </thead>
              <tbody>
                {rowsWithQty.map((row) => {
                  const bq = parseInt(row.buyQty) || 0;
                  const ltSq = parseInt(row.ltSellQty) || 0;
                  const stSq = parseInt(row.stSellQty) || 0;
                  const totalSq = ltSq + stSq;
                  const ltPl = ltSq > 0 && row.avgBuy > 0 ? (row.current - row.avgBuy) * ltSq : null;
                  const stPl = stSq > 0 && row.avgBuy > 0 ? (row.current - row.avgBuy) * stSq : null;
                  const totalPl = (ltPl || 0) + (stPl || 0);
                  const hasSellPl = ltPl !== null || stPl !== null;
                  const cLtPa = ltPl !== null ? calcPa(ltPl, row.avgBuy * ltSq, row.ltcgEarliestDate) : null;
                  const cStPa = stPl !== null ? calcPa(stPl, row.avgBuy * stSq, row.stcgEarliestDate) : null;
                  const cEarliest = [row.ltcgEarliestDate, row.stcgEarliestDate].filter(Boolean).sort()[0] || '';
                  const cTotalPa = hasSellPl ? calcPa(totalPl, row.avgBuy * totalSq, cEarliest) : null;
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
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600, color: totalSq ? '#f87171' : '#888' }}>{totalSq || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', color: ltSq ? '#f87171' : '#888', fontSize: '12px' }}>{ltSq || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', color: stSq ? '#f87171' : '#888', fontSize: '12px' }}>{stSq || '--'}</td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>
                        {bq > 0 && <div style={{ color: '#f87171' }}>-{formatINR(bq * row.current)}</div>}
                        {totalSq > 0 && <div style={{ color: '#4ade80' }}>+{formatINR(totalSq * row.current)}</div>}
                      </td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>
                        {ltPl !== null ? (
                          <div>
                            <div style={{ color: ltPl >= 0 ? '#4ade80' : '#f87171' }}>{ltPl >= 0 ? '+' : ''}{formatINR(ltPl)}</div>
                            {cLtPa !== null && <div style={{ fontSize: '11px', color: ltPl >= 0 ? '#4ade80' : '#f87171', opacity: 0.85 }}>{cLtPa >= 0 ? '+' : ''}{cLtPa.toFixed(1)}% p.a.</div>}
                          </div>
                        ) : ''}
                      </td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>
                        {stPl !== null ? (
                          <div>
                            <div style={{ color: stPl >= 0 ? '#4ade80' : '#f87171' }}>{stPl >= 0 ? '+' : ''}{formatINR(stPl)}</div>
                            {cStPa !== null && <div style={{ fontSize: '11px', color: stPl >= 0 ? '#4ade80' : '#f87171', opacity: 0.85 }}>{cStPa >= 0 ? '+' : ''}{cStPa.toFixed(1)}% p.a.</div>}
                          </div>
                        ) : ''}
                      </td>
                      <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 600 }}>
                        {hasSellPl ? (
                          <div>
                            <div style={{ color: totalPl >= 0 ? '#4ade80' : '#f87171' }}>{totalPl >= 0 ? '+' : ''}{formatINR(totalPl)}</div>
                            {row.avgBuy > 0 && <div style={{ fontSize: '11px', color: totalPl >= 0 ? '#4ade80' : '#f87171', opacity: 0.85 }}>{((row.current - row.avgBuy) / row.avgBuy * 100).toFixed(1)}%</div>}
                            {cTotalPa !== null && <div style={{ fontSize: '11px', color: totalPl >= 0 ? '#4ade80' : '#f87171', opacity: 0.85 }}>{cTotalPa >= 0 ? '+' : ''}{cTotalPa.toFixed(1)}% p.a.</div>}
                          </div>
                        ) : ''}
                      </td>
                    </tr>
                  );
                })}
                {(() => {
                  const capLtPL = rowsWithQty.reduce((sum, r) => {
                    const sq = parseInt(r.ltSellQty) || 0;
                    if (sq > 0 && r.avgBuy > 0 && r.current > 0) return sum + (r.current - r.avgBuy) * sq;
                    return sum;
                  }, 0);
                  const capStPL = rowsWithQty.reduce((sum, r) => {
                    const sq = parseInt(r.stSellQty) || 0;
                    if (sq > 0 && r.avgBuy > 0 && r.current > 0) return sum + (r.current - r.avgBuy) * sq;
                    return sum;
                  }, 0);
                  const capTotalPL = capLtPL + capStPL;
                  return (
                <tr style={{ borderTop: '2px solid #333355' }}>
                  <td colSpan={9} style={{ ...capTdStyle, fontWeight: 700, textAlign: 'right', paddingRight: '12px' }}>Grand Total</td>
                  <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, fontSize: '14px' }}>
                    {buyTotal > 0 && <div style={{ color: '#f87171' }}>-{formatINR(buyTotal)}</div>}
                    {sellTotal > 0 && <div style={{ color: '#4ade80' }}>+{formatINR(sellTotal)}</div>}
                  </td>
                  <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, fontSize: '14px' }}>
                    {capLtPL !== 0 && (
                      <div style={{ color: capLtPL >= 0 ? '#4ade80' : '#f87171' }}>
                        {capLtPL >= 0 ? '+' : ''}{formatINR(capLtPL)}
                      </div>
                    )}
                  </td>
                  <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, fontSize: '14px' }}>
                    {capStPL !== 0 && (
                      <div style={{ color: capStPL >= 0 ? '#4ade80' : '#f87171' }}>
                        {capStPL >= 0 ? '+' : ''}{formatINR(capStPL)}
                      </div>
                    )}
                  </td>
                  <td style={{ ...capTdStyle, textAlign: 'right', fontWeight: 700, fontSize: '14px' }}>
                    {capTotalPL !== 0 && (
                      <div style={{ color: capTotalPL >= 0 ? '#4ade80' : '#f87171' }}>
                        {capTotalPL >= 0 ? '+' : ''}{formatINR(capTotalPL)}
                      </div>
                    )}
                  </td>
                </tr>
                  );
                })()}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

const thStyle = { padding: '8px 6px', fontSize: '12px', fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.5px' };
const tdStyle = { padding: '8px 6px', color: 'var(--text)', fontSize: '13px' };
const qtyInputStyle = { width: '70px', padding: '4px 8px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: '4px', color: 'var(--text)', textAlign: 'right', fontSize: '13px' };
const capThStyle = { padding: '8px 6px', fontSize: '11px', fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: '0.5px', textAlign: 'left' };
const capTdStyle = { padding: '8px 6px', fontVariantNumeric: 'tabular-nums' };
