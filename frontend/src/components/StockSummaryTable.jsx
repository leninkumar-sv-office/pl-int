import React, { useState, useRef, useEffect, useCallback } from 'react';
import { getStockHistory } from '../services/api';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
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

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const formatDate = (dateStr) => {
  if (!dateStr) return '--';
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d.getTime())) return dateStr;
  const dd = String(d.getDate()).padStart(2, '0');
  const mon = MONTHS[d.getMonth()];
  const yyyy = d.getFullYear();
  return `${dd}-${mon}-${yyyy}`;
};

function WeekRangeBar({ low, high, current, buyPrice }) {
  if (!low || !high || low >= high) {
    return <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>;
  }
  const range = high - low;
  const currentPos = Math.max(0, Math.min(100, ((current - low) / range) * 100));
  const buyPos = Math.max(0, Math.min(100, ((buyPrice - low) / range) * 100));
  return (
    <div className="range-bar-container">
      <div className="range-bar">
        <div className="range-bar-fill" style={{ width: '100%' }} />
        <div className="range-marker buy" style={{ left: `${buyPos}%` }} title={`Avg Buy: ${formatINR(buyPrice)}`} />
        <div className="range-marker current" style={{ left: `${currentPos}%` }} title={`Current: ${formatINR(current)}`} />
      </div>
      <div className="range-labels">
        <span>{formatINR(low)}</span>
        <span>{formatINR(high)}</span>
      </div>
    </div>
  );
}

/* ── Held Lots column visibility config ─────────────────── */
const HELD_COL_DEFS = [
  { id: 'buyDate',   label: 'Buy Date' },
  { id: 'qty',       label: 'Qty' },
  { id: 'price',     label: 'Price' },
  { id: 'buyPrice',  label: 'Buy Price' },
  { id: 'totalCost', label: 'Total Cost' },
  { id: 'current',   label: 'Current' },
  { id: 'perUnit',   label: 'Per Unit' },
  { id: 'pl',        label: 'P&L' },
];
const HELD_DEFAULT_HIDDEN = ['price'];
const HELD_COL_LS_KEY = 'heldLotsHiddenCols';

function loadHeldHiddenCols() {
  try {
    const saved = localStorage.getItem(HELD_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(HELD_DEFAULT_HIDDEN);
}

/* ── Chart period tabs + formatting ──────────────────────── */
const CHART_PERIODS = ['1D', '5D', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX'];

function formatChartDate(dateStr, period) {
  const d = new Date(dateStr);
  if (period === '1d' || period === '5d') {
    return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  }
  if (period === '1m') return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: '2-digit' });
}

function StockChart({ symbol, exchange }) {
  const [period, setPeriod] = useState('1y');
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async (p) => {
    setLoading(true);
    try {
      const result = await getStockHistory(symbol, exchange, p);
      setData(result || []);
    } catch { setData([]); }
    finally { setLoading(false); }
  }, [symbol, exchange]);

  useEffect(() => { fetchData(period); }, []);

  const handlePeriod = (p) => {
    const lower = p.toLowerCase();
    setPeriod(lower);
    fetchData(lower);
  };

  const chartUp = data.length >= 2 && data[data.length - 1].close >= data[0].close;
  const chartColor = chartUp ? '#00d26a' : '#ff4757';
  const gradId = `grad-${symbol}-${exchange}`;

  return (
    <div>
      {/* Period tabs */}
      <div style={{ display: 'flex', gap: '2px', marginBottom: '8px' }}>
        {CHART_PERIODS.map(p => (
          <button key={p} onClick={() => handlePeriod(p)}
            style={{
              padding: '5px 12px', fontSize: '13px', fontWeight: 600, border: 'none', borderRadius: '6px', cursor: 'pointer',
              background: period === p.toLowerCase() ? 'var(--text)' : 'transparent',
              color: period === p.toLowerCase() ? 'var(--bg)' : 'var(--text-muted)',
            }}>
            {p}
          </button>
        ))}
      </div>
      {/* Chart */}
      <div style={{ height: '420px' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>Loading chart...</div>
        ) : data.length === 0 ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>No data available</div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={chartColor} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="date" tick={{ fontSize: 12, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                tickFormatter={(v) => formatChartDate(v, period)}
                interval="preserveStartEnd" minTickGap={60} />
              <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(0)} width={55} />
              <Tooltip
                contentStyle={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '11px' }}
                labelFormatter={(v) => {
                  const d = new Date(v);
                  return (period === '1d' || period === '5d')
                    ? d.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                    : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
                }}
                formatter={(value, name) => [formatINR(value), name.charAt(0).toUpperCase() + name.slice(1)]}
              />
              <Area type="monotone" dataKey="close" stroke={chartColor} strokeWidth={1.5} fill={`url(#${gradId})`} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

/* ── Expanded detail panel inside a stock row ───────────── */
function StockDetail({ stock, portfolio, transactions, onSell, onAddStock, onDividend, selectedLots, onToggleLot, onToggleAllLots }) {
  const heldLots = (portfolio || []).filter(
    (item) => item.holding.symbol === stock.symbol && item.holding.quantity > 0
  ).sort((a, b) => b.holding.buy_date.localeCompare(a.holding.buy_date));
  const soldTrades = (transactions || []).filter(
    (t) => t.symbol === stock.symbol
  ).sort((a, b) => b.sell_date.localeCompare(a.sell_date));
  const live = stock.live;
  const cp = live?.current_price || 0;

  const allLotsSelected = heldLots.length > 0 && heldLots.every(item => selectedLots.has(item.holding.id));
  const someLotsSelected = heldLots.some(item => selectedLots.has(item.holding.id));

  // Held lots column visibility
  const [hiddenHeldCols, setHiddenHeldCols] = useState(loadHeldHiddenCols);
  const [showColPicker, setShowColPicker] = useState(false);
  const colPickerRef = useRef(null);
  const hCol = (id) => !hiddenHeldCols.has(id);

  const toggleHeldCol = (id) => {
    setHiddenHeldCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      try { localStorage.setItem(HELD_COL_LS_KEY, JSON.stringify([...next])); } catch (_) {}
      return next;
    });
  };

  // Close column picker on outside click
  useEffect(() => {
    if (!showColPicker) return;
    const handler = (e) => { if (colPickerRef.current && !colPickerRef.current.contains(e.target)) setShowColPicker(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showColPicker]);

  // Sold transactions totals
  const totalSoldQty = soldTrades.reduce((sum, t) => sum + (t.quantity || 0), 0);
  const totalSoldPL = soldTrades.reduce((sum, t) => sum + (t.realized_pl || 0), 0);
  const totalSoldCost = soldTrades.reduce((sum, t) => sum + ((t.buy_price || 0) * (t.quantity || 0)), 0);
  const totalSoldPLPct = totalSoldCost > 0 ? (totalSoldPL / totalSoldCost * 100) : 0;
  // Cost-weighted average holding days for p.a. calculation
  const totalSoldWeightedDays = soldTrades.reduce((sum, t) => {
    const cost = (t.buy_price || 0) * (t.quantity || 0);
    if (cost <= 0 || !t.buy_date || !t.sell_date) return sum;
    const days = Math.floor((new Date(t.sell_date + 'T00:00:00') - new Date(t.buy_date + 'T00:00:00')) / (1000 * 60 * 60 * 24));
    return sum + cost * Math.max(days, 1);
  }, 0);
  const avgSoldDays = totalSoldCost > 0 ? totalSoldWeightedDays / totalSoldCost : 0;
  const totalSoldPLPa = avgSoldDays > 0 && totalSoldCost > 0
    ? (Math.pow(1 + totalSoldPL / totalSoldCost, 365 / avgSoldDays) - 1) * 100
    : null;

  return (
    <div style={{
      background: 'var(--bg)',
      borderTop: '1px solid var(--border)',
      padding: '20px 24px',
      display: 'flex',
      gap: '24px',
    }}>
      {/* Left side: details */}
      <div style={{ flex: '0 1 auto', minWidth: 0 }}>
      {/* Action buttons — prominent at top */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '20px',
        alignItems: 'center',
      }}>
        {heldLots.length > 0 && (
          <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>
            Quick actions:
          </span>
        )}
        <button
          className="btn btn-primary"
          onClick={(e) => { e.stopPropagation(); onAddStock({ symbol: stock.symbol, exchange: stock.exchange, name: stock.name }); }}
          style={{ fontWeight: 600 }}
        >
          + Buy {stock.symbol}
        </button>
        <button
          className="btn btn-ghost"
          onClick={(e) => { e.stopPropagation(); onDividend({ symbol: stock.symbol, exchange: stock.exchange }); }}
          style={{ fontWeight: 600 }}
        >
          + Dividend
        </button>
      </div>

      {/* 52-week range + extra stats */}
      {live && (
        <div style={{
          display: 'flex',
          gap: '32px',
          marginBottom: '20px',
          padding: '14px 16px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)',
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>52-Week Range</div>
            <WeekRangeBar low={live.week_52_low} high={live.week_52_high} current={cp} buyPrice={stock.avg_buy_price} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Invested</div>
            <div style={{ fontWeight: 600 }}>{formatINR(stock.total_invested)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Value</div>
            <div style={{ fontWeight: 600 }}>{formatINR(stock.current_value)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Unrealized P&L</div>
            <div style={{ fontWeight: 600, color: stock.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {stock.unrealized_pl >= 0 ? '+' : ''}{formatINR(stock.unrealized_pl)}
            </div>
          </div>
          {stock.realized_pl !== 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Realized P&L</div>
              <div style={{ fontWeight: 600, color: stock.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {stock.realized_pl >= 0 ? '+' : ''}{formatINR(stock.realized_pl)}
              </div>
            </div>
          )}
          {stock.total_dividend > 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Dividends</div>
              <div style={{ fontWeight: 600, color: 'var(--green)' }}>
                +{formatINR(stock.total_dividend)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Held Lots sub-table ────────────────────────── */}
      {heldLots.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span>Held Lots ({heldLots.length})</span>
            <span style={{ display: 'flex', gap: '8px', fontSize: '10px', fontWeight: 500 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#22c55e', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>LTCG (&gt;1yr)</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#f59e0b', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>STCG (&le;1yr)</span>
              </span>
            </span>
            {/* Column picker */}
            <div style={{ position: 'relative' }} ref={colPickerRef}>
              <button
                onClick={(e) => { e.stopPropagation(); setShowColPicker(v => !v); }}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '3px 8px',
                  fontSize: '11px',
                  color: 'var(--text-dim)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
                title="Show/hide columns"
              >
                <span style={{ fontSize: '13px' }}>&#9776;</span> Columns
              </button>
              {showColPicker && (
                <div style={{
                  position: 'absolute',
                  right: 0,
                  top: '100%',
                  marginTop: '4px',
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '8px 0',
                  zIndex: 100,
                  minWidth: '140px',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}>
                  {HELD_COL_DEFS.map(c => (
                    <label
                      key={c.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '4px 12px',
                        fontSize: '12px',
                        color: 'var(--text)',
                        cursor: 'pointer',
                        userSelect: 'none',
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <input
                        type="checkbox"
                        checked={hCol(c.id)}
                        onChange={() => toggleHeldCol(c.id)}
                        style={{ accentColor: 'var(--blue)' }}
                      />
                      {c.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'auto',
            width: 'fit-content',
            maxWidth: '100%',
          }}>
            <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <th style={{ ...heldTh, width: '30px', textAlign: 'center', padding: '8px 4px' }}>
                    <input
                      type="checkbox"
                      checked={allLotsSelected}
                      ref={(el) => { if (el) el.indeterminate = someLotsSelected && !allLotsSelected; }}
                      onChange={() => onToggleAllLots(heldLots.map(item => item.holding.id))}
                      style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
                      title="Select all lots for bulk sell"
                    />
                  </th>
                  {hCol('buyDate')   && <th style={heldTh}>Buy Date</th>}
                  {hCol('qty')       && <th style={heldTh}>Qty</th>}
                  {hCol('price')     && <th style={heldTh}>Price</th>}
                  {hCol('buyPrice')  && <th style={heldTh}>Buy Price</th>}
                  {hCol('totalCost') && <th style={heldTh}>Total Cost</th>}
                  {hCol('current')   && <th style={heldTh}>Current</th>}
                  {hCol('perUnit')   && <th style={heldTh}>Per Unit</th>}
                  {hCol('pl')        && <th style={heldTh}>P&L</th>}
                  <th style={heldTh}>Action</th>
                </tr>
              </thead>
              <tbody>
                {heldLots.map((item) => {
                  const h = item.holding;
                  const lotPL = cp > 0 ? (cp - h.buy_price) * h.quantity : 0;
                  const inProfit = cp > h.buy_price;
                  const isChecked = selectedLots.has(h.id);
                  const _daysSinceBuy = h.buy_date ? Math.floor((Date.now() - new Date(h.buy_date).getTime()) / 86400000) : 0;
                  const isLTCG = _daysSinceBuy > 365;
                  const ltcgColor = 'rgba(34,197,94,0.12)';   // green tint
                  const stcgColor = 'rgba(251,191,36,0.10)';  // amber tint
                  const ltcgBorder = '#22c55e';
                  const stcgBorder = '#f59e0b';
                  return (
                    <tr
                      key={h.id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        background: isChecked ? 'rgba(59,130,246,0.08)' : (isLTCG ? ltcgColor : stcgColor),
                        borderLeft: `3px solid ${isLTCG ? ltcgBorder : stcgBorder}`,
                      }}
                    >
                      <td style={{ textAlign: 'center', padding: '8px 4px', width: '30px' }}>
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => onToggleLot(h.id)}
                          style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
                        />
                      </td>
                      {hCol('buyDate') && (
                        <td style={heldTd}>
                          <div>{formatDate(h.buy_date)}</div>
                          <span style={{
                            fontSize: '9px',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: '3px',
                            color: isLTCG ? '#22c55e' : '#f59e0b',
                            background: isLTCG ? 'rgba(34,197,94,0.15)' : 'rgba(251,191,36,0.15)',
                            letterSpacing: '0.5px',
                          }}>
                            {isLTCG ? 'LTCG' : 'STCG'}
                          </span>
                        </td>
                      )}
                      {hCol('qty')       && <td style={{ ...heldTd, fontWeight: 600 }}>{h.quantity}</td>}
                      {hCol('price')     && <td style={heldTd}>{formatINR(h.price || h.buy_price)}</td>}
                      {hCol('buyPrice')  && <td style={heldTd}>{formatINR(h.buy_price)}</td>}
                      {hCol('totalCost') && <td style={heldTd}>{formatINR(h.buy_cost || (h.buy_price * h.quantity))}</td>}
                      {hCol('current')   && (
                        <td style={{ ...heldTd, color: inProfit ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                          {cp > 0 ? formatINR(cp) : '--'}
                        </td>
                      )}
                      {hCol('perUnit')   && (() => {
                        const unitGain = cp > 0 ? cp - h.buy_price : 0;
                        const unitPct = h.buy_price > 0 ? (unitGain / h.buy_price * 100) : 0;
                        const unitPa = _daysSinceBuy > 0 && h.buy_price > 0
                          ? (Math.pow(1 + unitGain / h.buy_price, 365 / _daysSinceBuy) - 1) * 100 : null;
                        const clr = unitGain >= 0 ? 'var(--green)' : 'var(--red)';
                        return (
                        <td style={heldTd}>
                          {cp > 0 ? (
                            <div>
                              <div style={{ fontWeight: 600, color: clr }}>{unitGain >= 0 ? '+' : ''}{formatINR(unitGain)}</div>
                              <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                {unitPct >= 0 ? '+' : ''}{unitPct.toFixed(2)}%
                              </div>
                              {unitPa !== null && (
                                <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                  {unitPa >= 0 ? '+' : ''}{unitPa.toFixed(2)}% p.a.
                                </div>
                              )}
                            </div>
                          ) : '--'}
                        </td>
                        );
                      })()}
                      {hCol('pl')        && (() => {
                        const lotCost = h.buy_price * h.quantity;
                        const lotPct = lotCost > 0 ? (lotPL / lotCost * 100) : 0;
                        const lotPa = _daysSinceBuy > 0 && lotCost > 0
                          ? (Math.pow(1 + lotPL / lotCost, 365 / _daysSinceBuy) - 1) * 100 : null;
                        const clr = lotPL >= 0 ? 'var(--green)' : 'var(--red)';
                        return (
                        <td style={heldTd}>
                          {cp > 0 ? (
                            <div>
                              <div style={{ fontWeight: 600, color: clr }}>{lotPL >= 0 ? '+' : ''}{formatINR(lotPL)}</div>
                              <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                {lotPct >= 0 ? '+' : ''}{lotPct.toFixed(2)}%
                              </div>
                              {lotPa !== null && (
                                <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                  {lotPa >= 0 ? '+' : ''}{lotPa.toFixed(2)}% p.a.
                                </div>
                              )}
                            </div>
                          ) : '--'}
                        </td>
                        );
                      })()}
                      <td style={heldTd}>
                        <button
                          className={`btn btn-sm ${inProfit ? 'btn-success' : 'btn-danger'}`}
                          onClick={(e) => { e.stopPropagation(); onSell(item); }}
                          style={{ minWidth: '48px', padding: '4px 10px' }}
                        >
                          Sell
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Sold Transactions sub-table ─────────────────── */}
      {soldTrades.length > 0 && (
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span>Sold Transactions ({soldTrades.length})</span>
            <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-dim)' }}>
              {totalSoldQty} share{totalSoldQty !== 1 ? 's' : ''}
            </span>
            <span style={{
              fontSize: '12px',
              fontWeight: 600,
              color: totalSoldPL >= 0 ? 'var(--green)' : 'var(--red)',
            }}>
              Net P&L: {totalSoldPL >= 0 ? '+' : ''}{formatINR(totalSoldPL)} ({totalSoldPLPct >= 0 ? '+' : ''}{totalSoldPLPct.toFixed(2)}%){totalSoldPLPa !== null && <span style={{ marginLeft: '6px', opacity: 0.85 }}>({totalSoldPLPa >= 0 ? '+' : ''}{totalSoldPLPa.toFixed(2)}% p.a.)</span>}
            </span>
          </div>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'auto',
            width: 'fit-content',
            maxWidth: '100%',
          }}>
            <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <th style={heldTh}>Buy Date</th>
                  <th style={heldTh}>Sell Date</th>
                  <th style={heldTh}>Qty</th>
                  <th style={heldTh}>Buy Price</th>
                  <th style={heldTh}>Sell Price</th>
                  <th style={heldTh}>Realized P&L</th>
                </tr>
              </thead>
              <tbody>
                {soldTrades.map((t, idx) => (
                  <tr key={t.id || idx} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={heldTd}>{formatDate(t.buy_date)}</td>
                    <td style={heldTd}>{formatDate(t.sell_date)}</td>
                    <td style={{ ...heldTd, fontWeight: 600 }}>{t.quantity}</td>
                    <td style={heldTd}>{formatINR(t.buy_price)}</td>
                    <td style={heldTd}>{formatINR(t.sell_price)}</td>
                    {(() => {
                      const sCost = t.buy_price * t.quantity;
                      const sPct = sCost > 0 ? (t.realized_pl / sCost * 100) : 0;
                      const sDays = t.buy_date && t.sell_date
                        ? Math.floor((new Date(t.sell_date + 'T00:00:00') - new Date(t.buy_date + 'T00:00:00')) / 86400000) : 0;
                      const sPa = sDays > 0 && sCost > 0
                        ? (Math.pow(1 + t.realized_pl / sCost, 365 / sDays) - 1) * 100 : null;
                      const clr = t.realized_pl >= 0 ? 'var(--green)' : 'var(--red)';
                      return (
                    <td style={heldTd}>
                      <div>
                        <div style={{ fontWeight: 600, color: clr }}>{t.realized_pl >= 0 ? '+' : ''}{formatINR(t.realized_pl)}</div>
                        <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                          {sPct >= 0 ? '+' : ''}{sPct.toFixed(2)}%
                        </div>
                        {sPa !== null && (
                          <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                            {sPa >= 0 ? '+' : ''}{sPa.toFixed(2)}% p.a.
                          </div>
                        )}
                      </div>
                    </td>
                      );
                    })()}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {heldLots.length === 0 && soldTrades.length === 0 && (
        <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
          No lot or transaction details available.
        </div>
      )}
      </div>
      {/* Right side: chart */}
      <div style={{ flex: '1 1 400px', minWidth: '300px', alignSelf: 'flex-start', position: 'sticky', top: '0' }}>
        <StockChart symbol={stock.symbol} exchange={stock.exchange} />
      </div>
    </div>
  );
}

const subTh = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: 'var(--text-dim)',
  fontWeight: 600,
  borderBottom: '1px solid var(--border)',
};

const subTd = {
  padding: '10px 14px',
  fontSize: '13px',
  verticalAlign: 'middle',
};

// Compact styles for Held Lots sub-table (tighter padding, fits content)
const heldTh = {
  padding: '7px 10px',
  textAlign: 'left',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: 'var(--text-dim)',
  fontWeight: 600,
  borderBottom: '1px solid var(--border)',
};
const heldTd = {
  padding: '7px 10px',
  fontSize: '13px',
  verticalAlign: 'middle',
};

// ── Column visibility config ──
const COL_DEFS = [
  { id: 'held',           label: 'Held',            grouped: false },
  { id: 'sold',           label: 'Sold',            grouped: false },
  { id: 'price',          label: 'Price',           grouped: false },
  { id: 'buyPrice',       label: 'Buy Price',       grouped: false },
  { id: 'totalCost',      label: 'Total Cost',      grouped: false },
  { id: 'w52Low',         label: '52W Low',         grouped: false },
  { id: 'currentPrice',   label: 'Current Price',   grouped: false },
  { id: 'w52High',        label: '52W High',        grouped: false },
  { id: 'unrealizedPF',   label: 'Unrealized PF',   grouped: true },
  { id: 'status',         label: 'Status',          grouped: false },
  { id: 'unrealizedLoss', label: 'Unrealized Loss', grouped: true },
  { id: 'unrealizedPL',   label: 'Unrealized P/L',  grouped: true },
  { id: 'realizedPL',     label: 'Realized P&L',    grouped: true },
  { id: 'dividends',      label: 'Dividends',       grouped: false },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'stockSummaryVisibleCols_v2';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  const DEFAULT_HIDDEN = ['sold', 'price', 'unrealizedPL', 'realizedPL', 'dividends'];
  return new Set(ALL_COL_IDS.filter(id => !DEFAULT_HIDDEN.includes(id)));
}

/* ── Column filter helpers ─────────────────────────────── */
function pctFromLow(stock) {
  const cp = stock.live?.current_price || 0;
  const low = stock.live?.week_52_low || 0;
  return (low > 0 && cp > 0) ? ((cp - low) / low * 100) : 9999;
}

function pctFromHigh(stock) {
  const cp = stock.live?.current_price || 0;
  const high = stock.live?.week_52_high || 0;
  return (high > 0 && cp > 0) ? ((high - cp) / high * 100) : 9999;
}

function getFilterValue(stock, colId) {
  switch (colId) {
    case 'held': return stock.total_held_qty;
    case 'sold': return stock.total_sold_qty;
    case 'buyPrice': return stock.avg_buy_price;
    case 'totalCost': return stock.total_invested;
    case 'currentPrice': return stock.live?.current_price || 0;
    case 'w52Low': return pctFromLow(stock);
    case 'w52High': return pctFromHigh(stock);
    case 'unrealizedPF': return stock.unrealized_profit || 0;
    case 'unrealizedLoss': return Math.abs(stock.unrealized_loss || 0);
    case 'dividends': return stock.total_dividend || 0;
    default: return null;
  }
}

function matchesPreset(stock, colId, preset) {
  switch (colId) {
    case 'w52Low': {
      const pct = pctFromLow(stock);
      if (preset === 'near5') return pct < 5;
      if (preset === 'near10') return pct < 10;
      if (preset === 'near20') return pct < 20;
      return true;
    }
    case 'w52High': {
      const pct = pctFromHigh(stock);
      if (preset === 'near5') return pct < 5;
      if (preset === 'near10') return pct < 10;
      if (preset === 'near20') return pct < 20;
      return true;
    }
    case 'status': {
      const hasHeld = stock.total_held_qty > 0;
      if (preset === 'profit') return hasHeld && stock.is_above_avg_buy;
      if (preset === 'loss') return hasHeld && !stock.is_above_avg_buy && !!stock.live;
      if (preset === 'sold') return stock.total_held_qty === 0;
      if (preset === 'ltcg') return (stock.ltcg_profitable_qty > 0) || (stock.ltcg_loss_qty > 0);
      if (preset === 'stcg') return (stock.stcg_profitable_qty > 0) || (stock.stcg_loss_qty > 0);
      return true;
    }
    case 'unrealizedPF': {
      const val = stock.unrealized_profit || 0;
      if (preset === '>1K') return val > 1000;
      if (preset === '>10K') return val > 10000;
      if (preset === '>50K') return val > 50000;
      if (preset === '>1L') return val > 100000;
      return true;
    }
    case 'unrealizedLoss': {
      const val = Math.abs(stock.unrealized_loss || 0);
      if (preset === '>1K') return val > 1000;
      if (preset === '>5K') return val > 5000;
      if (preset === '>10K') return val > 10000;
      return true;
    }
    default: return true;
  }
}

/* ── Sort by ₹ / % total / % p.a. support ─────────────── */
const PL_SORT_FIELDS = new Set([
  'unrealized_profit', 'ltcg_unrealized_profit', 'stcg_unrealized_profit',
  'unrealized_loss', 'ltcg_unrealized_loss', 'stcg_unrealized_loss',
  'unrealized_pl', 'ltcg_unrealized_pl', 'stcg_unrealized_pl',
  'realized_pl', 'ltcg_realized_pl', 'stcg_realized_pl',
]);
const SORT_MODES = ['inr', 'pct', 'pa'];
const SORT_MODE_LABELS = { inr: '₹', pct: '%', pa: '% p.a.' };

function sortPaVal(stock, field) {
  let val;
  switch (field) {
    case 'unrealized_profit': val = stock.unrealized_profit || 0; break;
    case 'ltcg_unrealized_profit': val = stock.ltcg_unrealized_profit || 0; break;
    case 'stcg_unrealized_profit': val = stock.stcg_unrealized_profit || 0; break;
    case 'unrealized_loss': val = stock.unrealized_loss || 0; break;
    case 'ltcg_unrealized_loss': val = stock.ltcg_unrealized_loss || 0; break;
    case 'stcg_unrealized_loss': val = stock.stcg_unrealized_loss || 0; break;
    case 'unrealized_pl': val = (stock.unrealized_profit || 0) + (stock.unrealized_loss || 0); break;
    case 'ltcg_unrealized_pl': val = (stock.ltcg_unrealized_profit || 0) + (stock.ltcg_unrealized_loss || 0); break;
    case 'stcg_unrealized_pl': val = (stock.stcg_unrealized_profit || 0) + (stock.stcg_unrealized_loss || 0); break;
    case 'realized_pl': val = stock.realized_pl || 0; break;
    case 'ltcg_realized_pl': val = stock.ltcg_realized_pl || 0; break;
    case 'stcg_realized_pl': val = stock.stcg_realized_pl || 0; break;
    default: return 0;
  }
  const pfx = field.startsWith('ltcg_') ? 'ltcg' : field.startsWith('stcg_') ? 'stcg' : 'total';
  const isRealized = field.includes('realized') && !field.includes('unrealized');
  let invested, diffDays;
  if (isRealized) {
    if (pfx === 'ltcg') {
      invested = stock.ltcg_sold_cost || 0;
      const eb = stock.ltcg_sold_earliest_buy, ls = stock.ltcg_sold_latest_sell;
      diffDays = (eb && ls) ? Math.floor((new Date(ls + 'T00:00:00') - new Date(eb + 'T00:00:00')) / 86400000) : 0;
    } else if (pfx === 'stcg') {
      invested = stock.stcg_sold_cost || 0;
      const eb = stock.stcg_sold_earliest_buy, ls = stock.stcg_sold_latest_sell;
      diffDays = (eb && ls) ? Math.floor((new Date(ls + 'T00:00:00') - new Date(eb + 'T00:00:00')) / 86400000) : 0;
    } else {
      invested = (stock.ltcg_sold_cost || 0) + (stock.stcg_sold_cost || 0);
      const buys = [stock.ltcg_sold_earliest_buy, stock.stcg_sold_earliest_buy].filter(Boolean);
      const sells = [stock.ltcg_sold_latest_sell, stock.stcg_sold_latest_sell].filter(Boolean);
      if (buys.length && sells.length) {
        diffDays = Math.floor((new Date(sells.sort().pop() + 'T00:00:00') - new Date(buys.sort()[0] + 'T00:00:00')) / 86400000);
      } else { diffDays = 0; }
    }
  } else {
    if (pfx === 'ltcg') {
      invested = stock.ltcg_invested || 0;
      const d = stock.ltcg_earliest_date;
      diffDays = d ? Math.floor((Date.now() - new Date(d + 'T00:00:00').getTime()) / 86400000) : 0;
    } else if (pfx === 'stcg') {
      invested = stock.stcg_invested || 0;
      const d = stock.stcg_earliest_date;
      diffDays = d ? Math.floor((Date.now() - new Date(d + 'T00:00:00').getTime()) / 86400000) : 0;
    } else {
      invested = stock.total_invested || 0;
      const dates = [stock.ltcg_earliest_date, stock.stcg_earliest_date].filter(Boolean);
      const earliest = dates.length ? dates.sort()[0] : null;
      diffDays = earliest ? Math.floor((Date.now() - new Date(earliest + 'T00:00:00').getTime()) / 86400000) : 0;
    }
  }
  if (invested <= 0 || diffDays <= 0) return val >= 0 ? -Infinity : Infinity;
  return (Math.pow(1 + val / invested, 365 / diffDays) - 1) * 100;
}

function sortPctVal(stock, field) {
  let val;
  switch (field) {
    case 'unrealized_profit': val = stock.unrealized_profit || 0; break;
    case 'ltcg_unrealized_profit': val = stock.ltcg_unrealized_profit || 0; break;
    case 'stcg_unrealized_profit': val = stock.stcg_unrealized_profit || 0; break;
    case 'unrealized_loss': val = stock.unrealized_loss || 0; break;
    case 'ltcg_unrealized_loss': val = stock.ltcg_unrealized_loss || 0; break;
    case 'stcg_unrealized_loss': val = stock.stcg_unrealized_loss || 0; break;
    case 'unrealized_pl': val = (stock.unrealized_profit || 0) + (stock.unrealized_loss || 0); break;
    case 'ltcg_unrealized_pl': val = (stock.ltcg_unrealized_profit || 0) + (stock.ltcg_unrealized_loss || 0); break;
    case 'stcg_unrealized_pl': val = (stock.stcg_unrealized_profit || 0) + (stock.stcg_unrealized_loss || 0); break;
    case 'realized_pl': val = stock.realized_pl || 0; break;
    case 'ltcg_realized_pl': val = stock.ltcg_realized_pl || 0; break;
    case 'stcg_realized_pl': val = stock.stcg_realized_pl || 0; break;
    default: return 0;
  }
  const pfx = field.startsWith('ltcg_') ? 'ltcg' : field.startsWith('stcg_') ? 'stcg' : 'total';
  const isRealized = field.includes('realized') && !field.includes('unrealized');
  let invested;
  if (isRealized) {
    if (pfx === 'ltcg') invested = stock.ltcg_sold_cost || 0;
    else if (pfx === 'stcg') invested = stock.stcg_sold_cost || 0;
    else invested = (stock.ltcg_sold_cost || 0) + (stock.stcg_sold_cost || 0);
  } else {
    if (pfx === 'ltcg') invested = stock.ltcg_invested || 0;
    else if (pfx === 'stcg') invested = stock.stcg_invested || 0;
    else invested = stock.total_invested || 0;
  }
  if (invested <= 0) return val >= 0 ? -Infinity : Infinity;
  return (val / invested) * 100;
}

const FILTER_INPUT_STYLE = {
  width: '55px',
  padding: '2px 4px',
  fontSize: '11px',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  borderRadius: '3px',
  color: 'var(--text)',
  outline: 'none',
  MozAppearance: 'textfield',
  WebkitAppearance: 'none',
};

const FILTER_SELECT_STYLE = {
  padding: '2px 4px',
  fontSize: '11px',
  background: 'var(--bg-input)',
  border: '1px solid var(--border)',
  borderRadius: '3px',
  color: 'var(--text)',
  outline: 'none',
  cursor: 'pointer',
  maxWidth: '110px',
};

/* ── Main Table ───────────────────────────────────────── */
export default function StockSummaryTable({ stocks, loading, onAddStock, portfolio, onSell, onBulkSell, onDividend, transactions, onImportContractNote, onImportDividendStatement, bulkSellDoneKey }) {
  const [sortField, setSortField] = useState('symbol');
  const [sortDir, setSortDir] = useState('asc');
  const [expandedSymbol, setExpandedSymbol] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [hideZeroHeld, setHideZeroHeld] = useState(true);
  const searchRef = useRef(null);
  const fileInputRef = useRef(null);
  const dividendFileInputRef = useRef(null);
  const [importing, setImporting] = useState(false);
  const [importingDividends, setImportingDividends] = useState(false);
  const [summaryCollapsed, setSummaryCollapsed] = useState(() => {
    try { return localStorage.getItem('stockSummaryCollapsed') !== 'false'; } catch { return true; }
  });
  const toggleSummary = () => setSummaryCollapsed(prev => { const next = !prev; localStorage.setItem('stockSummaryCollapsed', String(next)); return next; });
  // Bulk selection tracks individual lot (holding) IDs
  const [selectedLots, setSelectedLots] = useState(new Set());

  // Clear lot selection after bulk sell completes
  useEffect(() => {
    if (bulkSellDoneKey > 0) setSelectedLots(new Set());
  }, [bulkSellDoneKey]);

  // ── Column visibility ──
  const [visibleCols, setVisibleCols] = useState(loadVisibleCols);
  const [colPickerOpen, setColPickerOpen] = useState(false);
  const colPickerRef = useRef(null);
  const col = (id) => visibleCols.has(id);  // shorthand

  // ── Column filters ──
  const [filtersVisible, setFiltersVisible] = useState(false);
  const [columnFilters, setColumnFilters] = useState(() => {
    try { const s = localStorage.getItem('stockColumnFilters'); return s ? JSON.parse(s) : {}; } catch { return {}; }
  });

  // ── Sort mode toggle: inr → pct → pa ──
  const [sortMode, setSortMode] = useState('inr');
  const cycleSortMode = () => setSortMode(prev => SORT_MODES[(SORT_MODES.indexOf(prev) + 1) % SORT_MODES.length]);

  const toggleCol = (id) => {
    setVisibleCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      try { localStorage.setItem(LS_KEY, JSON.stringify([...next])); } catch (_) {}
      return next;
    });
  };
  const showAllCols = () => {
    const all = new Set(ALL_COL_IDS);
    setVisibleCols(all);
    try { localStorage.setItem(LS_KEY, JSON.stringify([...all])); } catch (_) {}
  };
  const hideAllCols = () => {
    setVisibleCols(new Set());
    try { localStorage.setItem(LS_KEY, JSON.stringify([])); } catch (_) {}
  };

  // Close dropdown on outside click
  useEffect(() => {
    if (!colPickerOpen) return;
    const handler = (e) => { if (colPickerRef.current && !colPickerRef.current.contains(e.target)) setColPickerOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [colPickerOpen]);

  // Persist column filters
  useEffect(() => {
    try { localStorage.setItem('stockColumnFilters', JSON.stringify(columnFilters)); } catch (_) {}
  }, [columnFilters]);

  const updateFilter = (colId, key, value) => {
    setColumnFilters(prev => {
      const next = { ...prev };
      if (!next[colId]) next[colId] = {};
      if (value === '' || value === undefined || value === 'all') {
        delete next[colId][key];
        if (Object.keys(next[colId]).length === 0) delete next[colId];
      } else {
        next[colId][key] = value;
      }
      return next;
    });
  };

  const clearAllFilters = () => setColumnFilters({});
  const activeFilterCount = Object.keys(columnFilters).length;

  useEffect(() => {
    if (searchRef.current) searchRef.current.focus();
  }, [stocks.length]);

  if (loading && stocks.length === 0) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading stock summary...
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📊</div>
        <h3>No stocks in your portfolio</h3>
        <p>Add your first stock to start tracking your investments.</p>
        <button className="btn btn-primary" onClick={() => onAddStock({})}>+ Add Your First Stock</button>
      </div>
    );
  }

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const toggleExpand = (symbol) => {
    setExpandedSymbol(prev => prev === symbol ? null : symbol);
  };

  // ── Lot-level bulk selection helpers ──
  const toggleLot = (lotId) => {
    setSelectedLots(prev => {
      const next = new Set(prev);
      if (next.has(lotId)) next.delete(lotId);
      else next.add(lotId);
      return next;
    });
  };

  const toggleAllLots = (lotIds) => {
    setSelectedLots(prev => {
      const allSelected = lotIds.every(id => prev.has(id));
      const next = new Set(prev);
      if (allSelected) {
        lotIds.forEach(id => next.delete(id));
      } else {
        lotIds.forEach(id => next.add(id));
      }
      return next;
    });
  };

  const clearSelection = () => setSelectedLots(new Set());

  const handleBulkSell = () => {
    if (!onBulkSell || selectedLots.size === 0) return;
    // Gather selected lots from portfolio
    const selectedItems = (portfolio || []).filter(
      item => selectedLots.has(item.holding.id) && item.holding.quantity > 0
    );
    if (selectedItems.length > 0) {
      onBulkSell(selectedItems);
    }
  };

  // Filter stocks by search query (matches symbol or name), held-units toggle, and column filters
  const q = searchQuery.trim().toLowerCase();
  const filtered = stocks.filter(s => {
    if (hideZeroHeld && s.total_held_qty <= 0) return false;
    if (q && !s.symbol.toLowerCase().includes(q) && !(s.name || '').toLowerCase().includes(q)) return false;
    // Column filters
    for (const [colId, f] of Object.entries(columnFilters)) {
      if (f.preset && f.preset !== 'all') {
        if (!matchesPreset(s, colId, f.preset)) return false;
      }
      const val = getFilterValue(s, colId);
      if (val !== null) {
        if (f.min !== undefined && f.min !== '' && val < Number(f.min)) return false;
        if (f.max !== undefined && f.max !== '' && val > Number(f.max)) return false;
      }
    }
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    let aVal, bVal;
    if (sortMode === 'pa' && PL_SORT_FIELDS.has(sortField)) {
      aVal = sortPaVal(a, sortField);
      bVal = sortPaVal(b, sortField);
    } else if (sortMode === 'pct' && PL_SORT_FIELDS.has(sortField)) {
      aVal = sortPctVal(a, sortField);
      bVal = sortPctVal(b, sortField);
    } else switch (sortField) {
      case 'symbol': aVal = a.symbol; bVal = b.symbol; break;
      case 'total_held_qty': aVal = a.total_held_qty; bVal = b.total_held_qty; break;
      case 'total_sold_qty': aVal = a.total_sold_qty; bVal = b.total_sold_qty; break;
      case 'total_invested': aVal = a.total_invested; bVal = b.total_invested; break;
      case 'current_value': aVal = a.current_value; bVal = b.current_value; break;
      case 'day_change_pct':
        aVal = a.live?.day_change_pct || 0; bVal = b.live?.day_change_pct || 0; break;
      case 'unrealized_profit':
        aVal = a.unrealized_profit || 0; bVal = b.unrealized_profit || 0; break;
      case 'ltcg_unrealized_profit':
        aVal = a.ltcg_unrealized_profit || 0; bVal = b.ltcg_unrealized_profit || 0; break;
      case 'stcg_unrealized_profit':
        aVal = a.stcg_unrealized_profit || 0; bVal = b.stcg_unrealized_profit || 0; break;
      case 'unrealized_loss':
        aVal = a.unrealized_loss || 0; bVal = b.unrealized_loss || 0; break;
      case 'ltcg_unrealized_loss':
        aVal = a.ltcg_unrealized_loss || 0; bVal = b.ltcg_unrealized_loss || 0; break;
      case 'stcg_unrealized_loss':
        aVal = a.stcg_unrealized_loss || 0; bVal = b.stcg_unrealized_loss || 0; break;
      case 'unrealized_pl':
        aVal = (a.unrealized_profit || 0) + (a.unrealized_loss || 0);
        bVal = (b.unrealized_profit || 0) + (b.unrealized_loss || 0); break;
      case 'ltcg_unrealized_pl':
        aVal = (a.ltcg_unrealized_profit || 0) + (a.ltcg_unrealized_loss || 0);
        bVal = (b.ltcg_unrealized_profit || 0) + (b.ltcg_unrealized_loss || 0); break;
      case 'stcg_unrealized_pl':
        aVal = (a.stcg_unrealized_profit || 0) + (a.stcg_unrealized_loss || 0);
        bVal = (b.stcg_unrealized_profit || 0) + (b.stcg_unrealized_loss || 0); break;
      case 'total_dividend':
        aVal = a.total_dividend || 0; bVal = b.total_dividend || 0; break;
      case 'realized_pl':
        aVal = a.realized_pl || 0; bVal = b.realized_pl || 0; break;
      case 'ltcg_realized_pl':
        aVal = a.ltcg_realized_pl || 0; bVal = b.ltcg_realized_pl || 0; break;
      case 'stcg_realized_pl':
        aVal = a.stcg_realized_pl || 0; bVal = b.stcg_realized_pl || 0; break;
      case 'week_52_low': {
        const aCP = a.live?.current_price || 0, aLow = a.live?.week_52_low || 0;
        const bCP = b.live?.current_price || 0, bLow = b.live?.week_52_low || 0;
        aVal = aLow > 0 && aCP > 0 ? ((aCP - aLow) / aLow * 100) : 9999;
        bVal = bLow > 0 && bCP > 0 ? ((bCP - bLow) / bLow * 100) : 9999;
        break;
      }
      case 'week_52_high': {
        const aCP2 = a.live?.current_price || 0, aHigh = a.live?.week_52_high || 0;
        const bCP2 = b.live?.current_price || 0, bHigh = b.live?.week_52_high || 0;
        aVal = aHigh > 0 && aCP2 > 0 ? ((aHigh - aCP2) / aHigh * 100) : 9999;
        bVal = bHigh > 0 && bCP2 > 0 ? ((bHigh - bCP2) / bHigh * 100) : 9999;
        break;
      }
      default: aVal = a.unrealized_profit; bVal = b.unrealized_profit;
    }
    if (typeof aVal === 'string') {
      return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
  });

  const stocksWithHeld = stocks.filter(s => s.total_held_qty > 0);
  const totalHeldStocks = stocksWithHeld.length;
  const inProfit = stocksWithHeld.filter(s => s.is_above_avg_buy).length;
  const inLoss = stocksWithHeld.filter(s => !s.is_above_avg_buy && s.live).length;

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span style={{ opacity: 0.3, fontSize: '10px' }}> ↕</span>;
    return <span style={{ fontSize: '10px' }}> {sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  // Dynamic column count: 2 always-on (expand + stock) + visible regular cols + visible grouped cols × 3
  const TOTAL_COLS = 2
    + COL_DEFS.filter(c => !c.grouped && visibleCols.has(c.id)).length
    + COL_DEFS.filter(c => c.grouped && visibleCols.has(c.id)).length * 3;
  const hasAnyGroupedCol = COL_DEFS.some(c => c.grouped && visibleCols.has(c.id));

  // ── Contract Note PDF Import (supports multiple files) ──
  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    // Reset the input so the same files can be re-selected
    e.target.value = '';
    const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) return;
    if (!onImportContractNote) return;
    setImporting(true);
    try {
      await onImportContractNote(pdfFiles);
    } catch (err) {
      // Error toast is handled in the parent
    } finally {
      setImporting(false);
    }
  };

  // ── Bank Statement Dividend Import (supports multiple files) ──
  const handleDividendFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    e.target.value = '';
    const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
    if (pdfFiles.length === 0) return;
    if (!onImportDividendStatement) return;
    setImportingDividends(true);
    try {
      await onImportDividendStatement(pdfFiles);
    } catch (err) {
      // Error toast handled in parent
    } finally {
      setImportingDividends(false);
    }
  };

  // Count selected lots info for the action bar
  const selectedCount = selectedLots.size;
  const selectedItems = selectedCount > 0
    ? (portfolio || []).filter(item => selectedLots.has(item.holding.id) && item.holding.quantity > 0)
    : [];
  const selectedQty = selectedItems.reduce((sum, item) => sum + item.holding.quantity, 0);
  const selectedPL = selectedItems.reduce((sum, item) => {
    const cp = item.live?.current_price || 0;
    return sum + (cp > 0 ? (cp - item.holding.buy_price) * item.holding.quantity : 0);
  }, 0);
  const selectedCost = selectedItems.reduce((sum, item) => sum + item.holding.buy_price * item.holding.quantity, 0);
  const selectedPLPct = selectedCost > 0 ? (selectedPL / selectedCost * 100) : 0;
  const selectedEarliestDate = selectedItems.reduce((min, item) => {
    const d = item.holding.buy_date;
    return d && d < min ? d : min;
  }, '9999-12-31');
  const selectedDays = selectedEarliestDate !== '9999-12-31' ? Math.floor((Date.now() - new Date(selectedEarliestDate + 'T00:00:00').getTime()) / 86400000) : 0;
  const selectedPLPa = selectedDays > 0 && selectedCost > 0 ? (Math.pow(1 + selectedPL / selectedCost, 365 / selectedDays) - 1) * 100 : null;

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title" onClick={toggleSummary} style={{ cursor: 'pointer', userSelect: 'none' }}>
          <span style={{ display: 'inline-block', width: '16px', fontSize: '10px', color: 'var(--text-muted)' }}>{summaryCollapsed ? '▶' : '▼'}</span>
          Stock Summary
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">
            {totalHeldStocks} stocks held
          </span>
          <span className="section-badge" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
            {inProfit} in profit
          </span>
          <span className="section-badge" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
            {inLoss} in loss
          </span>
          {/* PDF Import Button */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            multiple
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={importing}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              background: importing ? 'var(--bg-input)' : 'var(--blue)',
              color: importing ? 'var(--text-muted)' : '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: importing ? 'wait' : 'pointer',
              whiteSpace: 'nowrap',
              opacity: importing ? 0.7 : 1,
            }}
            title="Import transactions from SBICAP Securities contract note PDFs (select multiple)"
          >
            {importing ? 'Parsing PDFs...' : 'Import PDF'}
          </button>
          {/* Dividend Import Button */}
          <input
            ref={dividendFileInputRef}
            type="file"
            accept=".pdf"
            multiple
            onChange={handleDividendFileSelect}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => dividendFileInputRef.current?.click()}
            disabled={importingDividends}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              background: importingDividends ? 'var(--bg-input)' : '#8b5cf6',
              color: importingDividends ? 'var(--text-muted)' : '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: importingDividends ? 'wait' : 'pointer',
              whiteSpace: 'nowrap',
              opacity: importingDividends ? 0.7 : 1,
            }}
            title="Import dividends from SBI bank statement PDFs (select multiple)"
          >
            {importingDividends ? 'Parsing...' : 'Import Dividends'}
          </button>
        </div>
      </div>

      {/* ── Stock Summary Bar (matches MF dashboard pattern) ── */}
      {!summaryCollapsed && (() => {
        const heldStocks = stocks.filter(s => s.total_held_qty > 0);
        const sumInvested = heldStocks.reduce((s, st) => s + (st.total_invested || 0), 0);
        const sumCurrentVal = heldStocks.reduce((s, st) => s + (st.current_value || 0), 0);
        const sumUPL = heldStocks.reduce((s, st) => s + (st.unrealized_profit || 0) + (st.unrealized_loss || 0), 0);
        const uplPct = sumInvested > 0 ? (sumUPL / sumInvested) * 100 : 0;
        const sumRPL = stocks.reduce((s, st) => s + (st.realized_pl || 0), 0);
        const sumDiv = stocks.reduce((s, st) => s + (st.total_dividend || 0), 0);
        return (
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Invested</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(sumInvested)}</div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Value</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(sumCurrentVal)}</div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Unrealized P&L</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: sumUPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {sumUPL >= 0 ? '+' : ''}{formatINR(sumUPL)}
                <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4 }}>
                  ({uplPct >= 0 ? '+' : ''}{uplPct.toFixed(2)}%)
                </span>
              </div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Realized P&L</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: sumRPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {sumRPL >= 0 ? '+' : ''}{formatINR(sumRPL)}
              </div>
            </div>
            {sumDiv > 0 && (
              <div style={{ flex: '1 1 100px' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Dividends</div>
                <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--green)' }}>
                  +{formatINR(sumDiv)}
                </div>
              </div>
            )}
            <div style={{ flex: '1 1 80px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Stocks</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>
                {totalHeldStocks}
                <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4, color: 'var(--text-muted)' }}>
                  ({inProfit}↑ {inLoss}↓)
                </span>
              </div>
            </div>
          </div>
        );
      })()}

      {/* Search bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef}
            type="text"
            placeholder="Search stocks by symbol or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              padding: '8px 30px 8px 34px',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text)',
              fontSize: '13px',
              outline: 'none',
            }}
          />
          <span style={{
            position: 'absolute',
            left: '10px',
            top: '50%',
            transform: 'translateY(-50%)',
            color: 'var(--text-muted)',
            fontSize: '14px',
            pointerEvents: 'none',
          }}>
            &#x1F50D;
          </span>
          {searchQuery && (
            <span
              onClick={() => { setSearchQuery(''); if (searchRef.current) searchRef.current.focus(); }}
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                color: 'var(--text-muted)',
                fontSize: '16px',
                cursor: 'pointer',
                lineHeight: 1,
                userSelect: 'none',
              }}
              title="Clear search"
            >
              &#x2715;
            </span>
          )}
        </div>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          cursor: 'pointer',
          fontSize: '13px',
          color: 'var(--text-dim)',
          whiteSpace: 'nowrap',
          userSelect: 'none',
        }}>
          <input
            type="checkbox"
            checked={hideZeroHeld}
            onChange={(e) => setHideZeroHeld(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
          />
          Held only
        </label>
        {(q || hideZeroHeld) && (
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {filtered.length} of {stocks.length} stocks
          </span>
        )}
        {/* Filters toggle */}
        <button
          onClick={() => setFiltersVisible(v => !v)}
          style={{
            padding: '5px 10px',
            fontSize: '12px',
            background: filtersVisible ? 'var(--blue)' : 'var(--bg-input)',
            color: filtersVisible ? '#fff' : 'var(--text-dim)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            cursor: 'pointer',
            whiteSpace: 'nowrap',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            position: 'relative',
          }}
          title="Toggle column filters"
        >
          <span style={{ fontSize: '12px' }}>&#9663;</span> Filters
          {activeFilterCount > 0 && (
            <span style={{
              background: 'var(--red)',
              color: '#fff',
              fontSize: '10px',
              fontWeight: 700,
              borderRadius: '8px',
              padding: '0 5px',
              minWidth: '16px',
              textAlign: 'center',
              lineHeight: '16px',
            }}>
              {activeFilterCount}
            </span>
          )}
        </button>
        {activeFilterCount > 0 && (
          <span
            onClick={clearAllFilters}
            style={{
              fontSize: '11px',
              color: 'var(--blue)',
              cursor: 'pointer',
              textDecoration: 'underline',
              whiteSpace: 'nowrap',
            }}
          >
            Clear All
          </span>
        )}
        {/* Column picker */}
        <div ref={colPickerRef} style={{ position: 'relative' }}>
          <button
            onClick={() => setColPickerOpen(p => !p)}
            style={{
              padding: '5px 10px',
              fontSize: '12px',
              background: colPickerOpen ? 'var(--blue)' : 'var(--bg-input)',
              color: colPickerOpen ? '#fff' : 'var(--text-dim)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
            title="Show / hide columns"
          >
            <span style={{ fontSize: '13px' }}>&#9881;</span> Columns
          </button>
          {colPickerOpen && (
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: '4px',
              background: 'var(--bg-card)',
              border: '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              padding: '8px 0',
              zIndex: 100,
              minWidth: '180px',
              boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            }}>
              <div style={{ display: 'flex', gap: '8px', padding: '4px 12px 8px', borderBottom: '1px solid var(--border)' }}>
                <button onClick={showAllCols} style={{ fontSize: '11px', color: 'var(--blue)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Show All</button>
                <button onClick={hideAllCols} style={{ fontSize: '11px', color: 'var(--red)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}>Hide All</button>
              </div>
              {COL_DEFS.map(c => (
                <label
                  key={c.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '4px 12px',
                    cursor: 'pointer',
                    fontSize: '13px',
                    color: 'var(--text)',
                    userSelect: 'none',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-input)'}
                  onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <input
                    type="checkbox"
                    checked={visibleCols.has(c.id)}
                    onChange={() => toggleCol(c.id)}
                    style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
                  />
                  {c.label}
                  {c.grouped && <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 'auto' }}>3 cols</span>}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            {/* Row 1: grouped headers */}
            <tr>
              <th rowSpan={hasAnyGroupedCol ? 2 : undefined} style={{ width: '28px' }}></th>
              <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('symbol')} style={{ cursor: 'pointer' }}>
                Stock<SortIcon field="symbol" />
              </th>
              {col('held') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('total_held_qty')} style={{ cursor: 'pointer' }}>
                Held<SortIcon field="total_held_qty" />
              </th>}
              {col('sold') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('total_sold_qty')} style={{ cursor: 'pointer' }}>
                Sold<SortIcon field="total_sold_qty" />
              </th>}
              {col('price') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined}>Price</th>}
              {col('buyPrice') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined}>Buy Price</th>}
              {col('totalCost') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined}>Total Cost</th>}
              {col('w52Low') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('week_52_low')} style={{ cursor: 'pointer' }}>
                52W Low<SortIcon field="week_52_low" />
              </th>}
              {col('currentPrice') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('day_change_pct')} style={{ cursor: 'pointer' }}>
                Current Price<SortIcon field="day_change_pct" />
              </th>}
              {col('w52High') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('week_52_high')} style={{ cursor: 'pointer' }}>
                52W High<SortIcon field="week_52_high" />
              </th>}
              {col('unrealizedPF') && <th colSpan={3} onClick={() => handleSort('unrealized_profit')} style={{ cursor: 'pointer', textAlign: 'center', borderBottom: '1px solid var(--border)' }}>
                Unrealized PF<SortIcon field="unrealized_profit" />
                <span
                  onClick={(e) => { e.stopPropagation(); cycleSortMode(); }}
                  style={{ marginLeft: '6px', fontSize: '9px', padding: '1px 5px', borderRadius: '8px', background: sortMode !== 'inr' ? 'var(--blue)' : 'var(--bg-input)', color: sortMode !== 'inr' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', fontWeight: 600 }}
                  title={`Sorting by ${SORT_MODE_LABELS[sortMode]} — click to cycle`}
                >{SORT_MODE_LABELS[sortMode]}</span>
              </th>}
              {col('status') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} style={{ minWidth: '120px' }}>Status</th>}
              {col('unrealizedLoss') && <th colSpan={3} onClick={() => handleSort('unrealized_loss')} style={{ cursor: 'pointer', textAlign: 'center', borderBottom: '1px solid var(--border)' }}>
                Unrealized Loss<SortIcon field="unrealized_loss" />
                <span
                  onClick={(e) => { e.stopPropagation(); cycleSortMode(); }}
                  style={{ marginLeft: '6px', fontSize: '9px', padding: '1px 5px', borderRadius: '8px', background: sortMode !== 'inr' ? 'var(--blue)' : 'var(--bg-input)', color: sortMode !== 'inr' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', fontWeight: 600 }}
                  title={`Sorting by ${SORT_MODE_LABELS[sortMode]} — click to cycle`}
                >{SORT_MODE_LABELS[sortMode]}</span>
              </th>}
              {col('unrealizedPL') && <th colSpan={3} onClick={() => handleSort('unrealized_pl')} style={{ cursor: 'pointer', textAlign: 'center', borderBottom: '1px solid var(--border)' }}>
                Unrealized P/L<SortIcon field="unrealized_pl" />
                <span
                  onClick={(e) => { e.stopPropagation(); cycleSortMode(); }}
                  style={{ marginLeft: '6px', fontSize: '9px', padding: '1px 5px', borderRadius: '8px', background: sortMode !== 'inr' ? 'var(--blue)' : 'var(--bg-input)', color: sortMode !== 'inr' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', fontWeight: 600 }}
                  title={`Sorting by ${SORT_MODE_LABELS[sortMode]} — click to cycle`}
                >{SORT_MODE_LABELS[sortMode]}</span>
              </th>}
              {col('realizedPL') && <th colSpan={3} onClick={() => handleSort('realized_pl')} style={{ cursor: 'pointer', textAlign: 'center', borderBottom: '1px solid var(--border)' }}>
                Realized P&L<SortIcon field="realized_pl" />
                <span
                  onClick={(e) => { e.stopPropagation(); cycleSortMode(); }}
                  style={{ marginLeft: '6px', fontSize: '9px', padding: '1px 5px', borderRadius: '8px', background: sortMode !== 'inr' ? 'var(--blue)' : 'var(--bg-input)', color: sortMode !== 'inr' ? '#fff' : 'var(--text-muted)', cursor: 'pointer', fontWeight: 600 }}
                  title={`Sorting by ${SORT_MODE_LABELS[sortMode]} — click to cycle`}
                >{SORT_MODE_LABELS[sortMode]}</span>
              </th>}
              {col('dividends') && <th rowSpan={hasAnyGroupedCol ? 2 : undefined} onClick={() => handleSort('total_dividend')} style={{ cursor: 'pointer' }}>
                Dividends<SortIcon field="total_dividend" />
              </th>}
            </tr>
            {/* Row 2: sortable sub-column headers for visible grouped columns */}
            {hasAnyGroupedCol && <tr>
              {[
                { id: 'unrealizedPF',   total: 'unrealized_profit', ltcg: 'ltcg_unrealized_profit', stcg: 'stcg_unrealized_profit' },
                { id: 'unrealizedLoss', total: 'unrealized_loss',   ltcg: 'ltcg_unrealized_loss',   stcg: 'stcg_unrealized_loss' },
                { id: 'unrealizedPL',   total: 'unrealized_pl',     ltcg: 'ltcg_unrealized_pl',     stcg: 'stcg_unrealized_pl' },
                { id: 'realizedPL',     total: 'realized_pl',       ltcg: 'ltcg_realized_pl',       stcg: 'stcg_realized_pl' },
              ].filter(g => col(g.id)).map((group, i) => (
                <React.Fragment key={i}>
                  {[
                    { label: 'Total', field: group.total },
                    { label: 'LTCG',  field: group.ltcg },
                    { label: 'STCG',  field: group.stcg },
                  ].map(c => (
                    <th key={c.field} onClick={() => handleSort(c.field)}
                        style={{ fontSize: '10px', fontWeight: 500, padding: '2px 6px', opacity: 0.85, cursor: 'pointer', whiteSpace: 'nowrap', top: '36px' }}>
                      {c.label}<SortIcon field={c.field} />
                    </th>
                  ))}
                </React.Fragment>
              ))}
            </tr>}
            {/* ── Filter row ── */}
            {filtersVisible && (
              <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                <th></th>
                <th></th>
                {col('held') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min" value={columnFilters.held?.min ?? ''} onChange={e => updateFilter('held', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max" value={columnFilters.held?.max ?? ''} onChange={e => updateFilter('held', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('sold') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min" value={columnFilters.sold?.min ?? ''} onChange={e => updateFilter('sold', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max" value={columnFilters.sold?.max ?? ''} onChange={e => updateFilter('sold', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('price') && <th></th>}
                {col('buyPrice') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min ₹" value={columnFilters.buyPrice?.min ?? ''} onChange={e => updateFilter('buyPrice', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.buyPrice?.max ?? ''} onChange={e => updateFilter('buyPrice', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('totalCost') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min ₹" value={columnFilters.totalCost?.min ?? ''} onChange={e => updateFilter('totalCost', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.totalCost?.max ?? ''} onChange={e => updateFilter('totalCost', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('w52Low') && <th style={{ padding: '4px 6px' }}>
                  <select value={columnFilters.w52Low?.preset || 'all'} onChange={e => updateFilter('w52Low', 'preset', e.target.value)} style={FILTER_SELECT_STYLE} onClick={e => e.stopPropagation()}>
                    <option value="all">All</option>
                    <option value="near5">Near Low (&lt;5%)</option>
                    <option value="near10">&lt;10% from Low</option>
                    <option value="near20">&lt;20% from Low</option>
                  </select>
                </th>}
                {col('currentPrice') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min ₹" value={columnFilters.currentPrice?.min ?? ''} onChange={e => updateFilter('currentPrice', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.currentPrice?.max ?? ''} onChange={e => updateFilter('currentPrice', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('w52High') && <th style={{ padding: '4px 6px' }}>
                  <select value={columnFilters.w52High?.preset || 'all'} onChange={e => updateFilter('w52High', 'preset', e.target.value)} style={FILTER_SELECT_STYLE} onClick={e => e.stopPropagation()}>
                    <option value="all">All</option>
                    <option value="near5">Near High (&lt;5%)</option>
                    <option value="near10">&lt;10% from High</option>
                    <option value="near20">&lt;20% from High</option>
                  </select>
                </th>}
                {col('unrealizedPF') && <th colSpan={3} style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <select value={columnFilters.unrealizedPF?.preset || 'all'} onChange={e => updateFilter('unrealizedPF', 'preset', e.target.value)} style={FILTER_SELECT_STYLE} onClick={e => e.stopPropagation()}>
                      <option value="all">All</option>
                      <option value=">1K">&gt;₹1K</option>
                      <option value=">10K">&gt;₹10K</option>
                      <option value=">50K">&gt;₹50K</option>
                      <option value=">1L">&gt;₹1L</option>
                    </select>
                    <input type="number" placeholder="min ₹" value={columnFilters.unrealizedPF?.min ?? ''} onChange={e => updateFilter('unrealizedPF', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.unrealizedPF?.max ?? ''} onChange={e => updateFilter('unrealizedPF', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('status') && <th style={{ padding: '4px 6px' }}>
                  <select value={columnFilters.status?.preset || 'all'} onChange={e => updateFilter('status', 'preset', e.target.value)} style={FILTER_SELECT_STYLE} onClick={e => e.stopPropagation()}>
                    <option value="all">All</option>
                    <option value="profit">In Profit</option>
                    <option value="loss">In Loss</option>
                    <option value="sold">Fully Sold</option>
                    <option value="ltcg">Has LTCG</option>
                    <option value="stcg">Has STCG</option>
                  </select>
                </th>}
                {col('unrealizedLoss') && <th colSpan={3} style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '4px', alignItems: 'center', flexWrap: 'wrap' }}>
                    <select value={columnFilters.unrealizedLoss?.preset || 'all'} onChange={e => updateFilter('unrealizedLoss', 'preset', e.target.value)} style={FILTER_SELECT_STYLE} onClick={e => e.stopPropagation()}>
                      <option value="all">All</option>
                      <option value=">1K">Loss &gt;₹1K</option>
                      <option value=">5K">Loss &gt;₹5K</option>
                      <option value=">10K">Loss &gt;₹10K</option>
                    </select>
                    <input type="number" placeholder="min ₹" value={columnFilters.unrealizedLoss?.min ?? ''} onChange={e => updateFilter('unrealizedLoss', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.unrealizedLoss?.max ?? ''} onChange={e => updateFilter('unrealizedLoss', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
                {col('unrealizedPL') && <th colSpan={3}></th>}
                {col('realizedPL') && <th colSpan={3}></th>}
                {col('dividends') && <th style={{ padding: '4px 6px' }}>
                  <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
                    <input type="number" placeholder="min ₹" value={columnFilters.dividends?.min ?? ''} onChange={e => updateFilter('dividends', 'min', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                    <input type="number" placeholder="max ₹" value={columnFilters.dividends?.max ?? ''} onChange={e => updateFilter('dividends', 'max', e.target.value)} style={FILTER_INPUT_STYLE} onClick={e => e.stopPropagation()} />
                  </div>
                </th>}
              </tr>
            )}
          </thead>
          <tbody>
            {sorted.map((stock) => {
              const live = stock.live;
              const currentPrice = live?.current_price || 0;
              const hasHeld = stock.total_held_qty > 0;
              const isExpanded = expandedSymbol === stock.symbol;

              // Shared row-level: earliest buy date, holding duration, duration string
              const _heldLots = (portfolio || []).filter(item => item.holding.symbol === stock.symbol && item.holding.quantity > 0);
              const _earliestDate = _heldLots.reduce((min, item) => { const d = item.holding.buy_date; return d && d < min ? d : min; }, '9999-12-31');
              let _durationStr = '';
              let _diffDays = 0;
              if (_earliestDate !== '9999-12-31') {
                const _start = new Date(_earliestDate + 'T00:00:00');
                const _now = new Date();
                _diffDays = Math.floor((_now - _start) / (1000 * 60 * 60 * 24));
                if (_diffDays >= 365) {
                  const y = Math.floor(_diffDays / 365);
                  const m = Math.floor((_diffDays % 365) / 30);
                  _durationStr = `in ${y}y${m > 0 ? ` ${m}m` : ''}`;
                } else if (_diffDays >= 30) {
                  const m = Math.floor(_diffDays / 30);
                  const d = _diffDays % 30;
                  _durationStr = `in ${m}m${d > 0 ? ` ${d}d` : ''}`;
                } else {
                  _durationStr = `in ${_diffDays}d`;
                }
              }
              const _calcPa = (val) => {
                if (_diffDays <= 0 || stock.total_invested <= 0) return null;
                return (Math.pow(1 + val / stock.total_invested, 365 / _diffDays) - 1) * 100;
              };
              const _pctOf = (val) => stock.total_invested > 0 ? (val / stock.total_invested) * 100 : 0;

              // ── Per-category (LTCG/STCG) unrealized helpers ──
              const _makeDateHelpers = (dateStr) => {
                let diffDays = 0, durStr = '';
                if (dateStr) {
                  const s = new Date(dateStr + 'T00:00:00');
                  const n = new Date();
                  diffDays = Math.floor((n - s) / (1000 * 60 * 60 * 24));
                  if (diffDays >= 365) {
                    const y = Math.floor(diffDays / 365), m = Math.floor((diffDays % 365) / 30);
                    durStr = `in ${y}y${m > 0 ? ` ${m}m` : ''}`;
                  } else if (diffDays >= 30) {
                    const m = Math.floor(diffDays / 30), d = diffDays % 30;
                    durStr = `in ${m}m${d > 0 ? ` ${d}d` : ''}`;
                  } else {
                    durStr = `in ${diffDays}d`;
                  }
                }
                return { diffDays, durStr };
              };
              const _ltcgH = _makeDateHelpers(stock.ltcg_earliest_date);
              const _stcgH = _makeDateHelpers(stock.stcg_earliest_date);
              const _ltcgPctOf = (val) => stock.ltcg_invested > 0 ? (val / stock.ltcg_invested) * 100 : 0;
              const _stcgPctOf = (val) => stock.stcg_invested > 0 ? (val / stock.stcg_invested) * 100 : 0;
              const _ltcgCalcPa = (val) => {
                if (_ltcgH.diffDays <= 0 || stock.ltcg_invested <= 0) return null;
                return (Math.pow(1 + val / stock.ltcg_invested, 365 / _ltcgH.diffDays) - 1) * 100;
              };
              const _stcgCalcPa = (val) => {
                if (_stcgH.diffDays <= 0 || stock.stcg_invested <= 0) return null;
                return (Math.pow(1 + val / stock.stcg_invested, 365 / _stcgH.diffDays) - 1) * 100;
              };

              // Sold transaction duration: earliest buy_date → latest sell_date
              const _soldTxns = (transactions || []).filter(t => t.symbol === stock.symbol);
              const _soldEarliestBuy = _soldTxns.reduce((min, t) => { const d = t.buy_date; return d && d < min ? d : min; }, '9999-12-31');
              const _soldLatestSell = _soldTxns.reduce((max, t) => { const d = t.sell_date; return d && d > max ? d : max; }, '0000-01-01');
              let _soldDurationStr = '';
              let _soldDiffDays = 0;
              if (_soldEarliestBuy !== '9999-12-31' && _soldLatestSell !== '0000-01-01') {
                const _sStart = new Date(_soldEarliestBuy + 'T00:00:00');
                const _sEnd = new Date(_soldLatestSell + 'T00:00:00');
                _soldDiffDays = Math.floor((_sEnd - _sStart) / (1000 * 60 * 60 * 24));
                if (_soldDiffDays >= 365) {
                  const y = Math.floor(_soldDiffDays / 365);
                  const m = Math.floor((_soldDiffDays % 365) / 30);
                  _soldDurationStr = `in ${y}y${m > 0 ? ` ${m}m` : ''}`;
                } else if (_soldDiffDays >= 30) {
                  const m = Math.floor(_soldDiffDays / 30);
                  const d = _soldDiffDays % 30;
                  _soldDurationStr = `in ${m}m${d > 0 ? ` ${d}d` : ''}`;
                } else {
                  _soldDurationStr = `in ${_soldDiffDays}d`;
                }
              }
              const _soldCost = _soldTxns.reduce((sum, t) => sum + (t.buy_price * t.quantity), 0);
              const _calcSoldPa = (val) => {
                if (_soldDiffDays <= 0 || _soldCost <= 0) return null;
                return (Math.pow(1 + val / _soldCost, 365 / _soldDiffDays) - 1) * 100;
              };
              const _pctOfSold = (val) => _soldCost > 0 ? (val / _soldCost) * 100 : 0;

              // ── Per-category (LTCG/STCG) realized helpers ──
              const _makeSoldDateHelpers = (earliestBuy, latestSell) => {
                let diffDays = 0, durStr = '';
                if (earliestBuy && latestSell) {
                  const s = new Date(earliestBuy + 'T00:00:00');
                  const e = new Date(latestSell + 'T00:00:00');
                  diffDays = Math.floor((e - s) / (1000 * 60 * 60 * 24));
                  if (diffDays >= 365) {
                    const y = Math.floor(diffDays / 365), m = Math.floor((diffDays % 365) / 30);
                    durStr = `in ${y}y${m > 0 ? ` ${m}m` : ''}`;
                  } else if (diffDays >= 30) {
                    const m = Math.floor(diffDays / 30), d = diffDays % 30;
                    durStr = `in ${m}m${d > 0 ? ` ${d}d` : ''}`;
                  } else {
                    durStr = `in ${diffDays}d`;
                  }
                }
                return { diffDays, durStr };
              };
              const _ltcgSold = _makeSoldDateHelpers(stock.ltcg_sold_earliest_buy, stock.ltcg_sold_latest_sell);
              const _stcgSold = _makeSoldDateHelpers(stock.stcg_sold_earliest_buy, stock.stcg_sold_latest_sell);
              const _ltcgSoldPctOf = (val) => stock.ltcg_sold_cost > 0 ? (val / stock.ltcg_sold_cost) * 100 : 0;
              const _stcgSoldPctOf = (val) => stock.stcg_sold_cost > 0 ? (val / stock.stcg_sold_cost) * 100 : 0;
              const _ltcgCalcSoldPa = (val) => {
                if (_ltcgSold.diffDays <= 0 || stock.ltcg_sold_cost <= 0) return null;
                return (Math.pow(1 + val / stock.ltcg_sold_cost, 365 / _ltcgSold.diffDays) - 1) * 100;
              };
              const _stcgCalcSoldPa = (val) => {
                if (_stcgSold.diffDays <= 0 || stock.stcg_sold_cost <= 0) return null;
                return (Math.pow(1 + val / stock.stcg_sold_cost, 365 / _stcgSold.diffDays) - 1) * 100;
              };

              return (
                <React.Fragment key={stock.symbol}>
                  {/* ── Main summary row (clickable) ─────────── */}
                  <tr
                    className={stock.is_above_avg_buy && hasHeld ? 'highlight-profit' : ''}
                    style={{
                      opacity: hasHeld ? 1 : 0.6,
                      cursor: 'pointer',
                      background: isExpanded ? 'var(--bg-card-hover)' : undefined,
                    }}
                    onClick={() => toggleExpand(stock.symbol)}
                  >
                    {/* Expand indicator */}
                    <td style={{ padding: '14px 4px 14px 16px', width: '28px', fontSize: '14px', color: 'var(--text-dim)' }}>
                      {isExpanded ? '▾' : '▸'}
                    </td>
                    <td>
                      <div className="stock-symbol">
                        {stock.symbol}
                        <span className="stock-exchange">{stock.exchange}</span>
                        {live?.is_manual && <span className="manual-badge">Manual</span>}
                      </div>
                      <div className="stock-name">{stock.name}</div>
                    </td>
                    {col('held') && <td>
                      <div style={{ fontWeight: 700, fontSize: '15px' }}>
                        {stock.total_held_qty > 0 ? stock.total_held_qty : '-'}
                      </div>
                      {stock.num_held_lots > 1 && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {stock.num_held_lots} lots
                        </div>
                      )}
                    </td>}
                    {col('sold') && <td>
                      {stock.total_sold_qty > 0 ? (
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--yellow)' }}>
                            {stock.total_sold_qty}
                          </div>
                          {stock.num_sold_lots > 1 && (
                            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              {stock.num_sold_lots} trades
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>}
                    {col('price') && <td>{hasHeld ? formatINR(stock.avg_price) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>}
                    {col('buyPrice') && <td>{hasHeld ? formatINR(stock.avg_buy_price) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>}
                    {col('totalCost') && <td>{hasHeld ? formatINR(stock.total_invested) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>}
                    {col('w52Low') && <td>
                      {live?.week_52_low ? (() => {
                        const nearLow = currentPrice > 0 && currentPrice <= live.week_52_low * 1.05;
                        const pctFromLow = currentPrice > 0 && live.week_52_low > 0
                          ? ((currentPrice - live.week_52_low) / live.week_52_low * 100) : 0;
                        return (
                          <div>
                            <div style={{
                              fontSize: '13px',
                              color: nearLow ? 'var(--red)' : 'var(--text)',
                              fontWeight: nearLow ? 600 : 400,
                            }}>
                              {formatINR(live.week_52_low)}
                            </div>
                            {currentPrice > 0 && (() => {
                              const delta = currentPrice - live.week_52_low;
                              const amt = fmtAmt(delta) || '+₹0';
                              return (
                                <div style={{ fontSize: '10px', color: delta >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                  {delta >= 0 ? '+' : ''}{pctFromLow.toFixed(2)}%, {amt}
                                </div>
                              );
                            })()}
                          </div>
                        );
                      })() : (
                        <span style={{ color: 'var(--text-muted)' }}>--</span>
                      )}
                    </td>}
                    {col('currentPrice') && <td>
                      {live ? (
                        <div>
                          <div style={{
                            fontWeight: 600,
                            color: hasHeld
                              ? (currentPrice >= stock.avg_buy_price ? 'var(--green)' : 'var(--red)')
                              : 'var(--text)',
                          }}>
                            {formatINR(currentPrice)}
                          </div>
                          {(() => {
                            const pct = live.day_change_pct || 0;
                            const amt = fmtAmt(live.day_change || 0) || '+₹0';
                            return (
                              <div style={{ fontSize: '10px', color: pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                1D: {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%, {amt}
                              </div>
                            );
                          })()}
                          {live.week_change_pct !== 0 && (() => {
                            const amt = fmtAmt(currentPrice * live.week_change_pct / (100 + live.week_change_pct));
                            return (
                              <div style={{ fontSize: '10px', color: live.week_change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                7D: {live.week_change_pct >= 0 ? '+' : ''}{live.week_change_pct.toFixed(2)}%{amt ? `, ${amt}` : ''}
                              </div>
                            );
                          })()}
                          {live.month_change_pct !== 0 && (() => {
                            const amt = fmtAmt(currentPrice * live.month_change_pct / (100 + live.month_change_pct));
                            return (
                              <div style={{ fontSize: '10px', color: live.month_change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                1M: {live.month_change_pct >= 0 ? '+' : ''}{live.month_change_pct.toFixed(2)}%{amt ? `, ${amt}` : ''}
                              </div>
                            );
                          })()}
                        </div>
                      ) : (
                        <span style={{ color: stock.price_error ? 'var(--red)' : 'var(--text-muted)', fontSize: '12px' }}>
                          {stock.price_error ? 'N/A' : '--'}
                        </span>
                      )}
                    </td>}
                    {col('w52High') && <td>
                      {live?.week_52_high ? (() => {
                        const nearHigh = currentPrice > 0 && currentPrice >= live.week_52_high * 0.95;
                        const pctFromHigh = currentPrice > 0 && live.week_52_high > 0
                          ? ((live.week_52_high - currentPrice) / live.week_52_high * 100) : 0;
                        return (
                          <div>
                            <div style={{
                              fontSize: '13px',
                              color: nearHigh ? 'var(--green)' : 'var(--text)',
                              fontWeight: nearHigh ? 600 : 400,
                            }}>
                              {formatINR(live.week_52_high)}
                            </div>
                            {currentPrice > 0 && (() => {
                              const delta = currentPrice - live.week_52_high;
                              const amt = fmtAmt(delta) || '-₹0';
                              return (
                                <div style={{ fontSize: '10px', color: delta >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                  {delta >= 0 ? '+' : ''}{(-pctFromHigh).toFixed(2)}%, {amt}
                                </div>
                              );
                            })()}
                          </div>
                        );
                      })() : (
                        <span style={{ color: 'var(--text-muted)' }}>--</span>
                      )}
                    </td>}
                    {/* ── Unrealized PF: Total | LTCG | STCG ── */}
                    {col('unrealizedPF') && (() => {
                      const nw = { whiteSpace: 'nowrap' };
                      const val = stock.unrealized_profit || 0;
                      const ltcg = stock.ltcg_unrealized_profit || 0;
                      const stcg = stock.stcg_unrealized_profit || 0;
                      const show = hasHeld && val > 0;
                      const pfPct = show ? _pctOf(val) : 0;
                      const pfPa = show ? _calcPa(val) : null;
                      const ltcgPct = ltcg > 0 ? _ltcgPctOf(ltcg) : 0;
                      const ltcgPa = ltcg > 0 ? _ltcgCalcPa(ltcg) : null;
                      const stcgPct = stcg > 0 ? _stcgPctOf(stcg) : 0;
                      const stcgPa = stcg > 0 ? _stcgCalcPa(stcg) : null;
                      const subCell = (v, qty, pct, dur, pa) => v > 0 ? (
                        <td style={nw}>
                          <div style={{ fontWeight: 600, color: 'var(--green)', ...nw }}>+{formatINR(v)}</div>
                          {qty > 0 && <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85, ...nw }}>on {qty} units</div>}
                          <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85, ...nw }}>+{pct.toFixed(1)}%{dur ? ` ${dur}` : ''}</div>
                          {pa !== null && <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85, ...nw }}>+{pa.toFixed(1)}% p.a.</div>}
                        </td>
                      ) : <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>;
                      return show ? (
                        <>
                          {subCell(val, stock.profitable_qty, pfPct, _durationStr, pfPa)}
                          {subCell(ltcg, stock.ltcg_profitable_qty, ltcgPct, _ltcgH.durStr, ltcgPa)}
                          {subCell(stcg, stock.stcg_profitable_qty, stcgPct, _stcgH.durStr, stcgPa)}
                        </>
                      ) : (
                        <>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                        </>
                      );
                    })()}

                    {col('status') && <td style={{ whiteSpace: 'nowrap' }}>
                      {hasHeld && (stock.profitable_qty > 0 || stock.loss_qty > 0) ? (
                        <div>
                          {stock.profitable_qty > 0 && (
                            <div className="sell-tag" style={{ marginBottom: '2px' }}>
                              ▲ Can Sell {stock.profitable_qty}
                              {((stock.ltcg_profitable_qty || 0) > 0 || (stock.stcg_profitable_qty || 0) > 0) && (
                                <span style={{ marginLeft: '4px' }}>
                                  ({[
                                    (stock.ltcg_profitable_qty || 0) > 0 && `L:${stock.ltcg_profitable_qty}`,
                                    (stock.stcg_profitable_qty || 0) > 0 && `S:${stock.stcg_profitable_qty}`,
                                  ].filter(Boolean).join(' · ')})
                                </span>
                              )}
                            </div>
                          )}
                          {stock.loss_qty > 0 && (
                            <div style={{ fontSize: '10px', color: 'var(--red)', marginTop: stock.profitable_qty > 0 ? '3px' : '0', display: 'flex', gap: '6px', alignItems: 'center' }}>
                              <span>{stock.loss_qty} in loss</span>
                              {(stock.ltcg_loss_qty || 0) > 0 && (
                                <span style={{ color: '#22c55e', fontWeight: 600 }}>L:{stock.ltcg_loss_qty}</span>
                              )}
                              {(stock.stcg_loss_qty || 0) > 0 && (
                                <span style={{ color: '#f59e0b', fontWeight: 600 }}>S:{stock.stcg_loss_qty}</span>
                              )}
                            </div>
                          )}
                        </div>
                      ) : hasHeld ? (
                        <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>No Price</span>
                      ) : (
                        <span style={{
                          fontSize: '11px',
                          color: 'var(--text-muted)',
                          background: 'var(--bg-input)',
                          padding: '2px 8px',
                          borderRadius: '10px',
                        }}>
                          Fully Sold
                        </span>
                      )}
                    </td>}

                    {/* ── Unrealized Loss: Total | LTCG | STCG ── */}
                    {col('unrealizedLoss') && (() => {
                      const nw = { whiteSpace: 'nowrap' };
                      const val = stock.unrealized_loss || 0;
                      const ltcg = stock.ltcg_unrealized_loss || 0;
                      const stcg = stock.stcg_unrealized_loss || 0;
                      const show = hasHeld && val < 0;
                      const lossPct = show ? _pctOf(val) : 0;
                      const lossPa = show ? _calcPa(val) : null;
                      const ltcgPct = ltcg < 0 ? _ltcgPctOf(ltcg) : 0;
                      const ltcgPa = ltcg < 0 ? _ltcgCalcPa(ltcg) : null;
                      const stcgPct = stcg < 0 ? _stcgPctOf(stcg) : 0;
                      const stcgPa = stcg < 0 ? _stcgCalcPa(stcg) : null;
                      const subCell = (v, qty, pct, dur, pa) => v < 0 ? (
                        <td style={nw}>
                          <div style={{ fontWeight: 600, color: 'var(--red)', ...nw }}>{formatINR(v)}</div>
                          {qty > 0 && <div style={{ fontSize: '11px', color: 'var(--red)', opacity: 0.85, ...nw }}>on {qty} units</div>}
                          <div style={{ fontSize: '11px', color: 'var(--red)', opacity: 0.85, ...nw }}>{pct.toFixed(1)}%{dur ? ` ${dur}` : ''}</div>
                          {pa !== null && <div style={{ fontSize: '11px', color: 'var(--red)', opacity: 0.85, ...nw }}>{pa.toFixed(1)}% p.a.</div>}
                        </td>
                      ) : <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>;
                      return show ? (
                        <>
                          {subCell(val, stock.loss_qty, lossPct, _durationStr, lossPa)}
                          {subCell(ltcg, stock.ltcg_loss_qty, ltcgPct, _ltcgH.durStr, ltcgPa)}
                          {subCell(stcg, stock.stcg_loss_qty, stcgPct, _stcgH.durStr, stcgPa)}
                        </>
                      ) : (
                        <>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                        </>
                      );
                    })()}

                    {/* ── Unrealized P/L: Total | LTCG | STCG ── */}
                    {col('unrealizedPL') && (() => {
                      const nw = { whiteSpace: 'nowrap' };
                      const upl = (stock.unrealized_profit || 0) + (stock.unrealized_loss || 0);
                      const ltcg = (stock.ltcg_unrealized_profit || 0) + (stock.ltcg_unrealized_loss || 0);
                      const stcg = (stock.stcg_unrealized_profit || 0) + (stock.stcg_unrealized_loss || 0);
                      const uplPct = hasHeld ? _pctOf(upl) : 0;
                      const uplPa = hasHeld ? _calcPa(upl) : null;
                      const ltcgPct = hasHeld && stock.ltcg_invested > 0 ? _ltcgPctOf(ltcg) : 0;
                      const ltcgPa = hasHeld && ltcg !== 0 ? _ltcgCalcPa(ltcg) : null;
                      const stcgPct = hasHeld && stock.stcg_invested > 0 ? _stcgPctOf(stcg) : 0;
                      const stcgPa = hasHeld && stcg !== 0 ? _stcgCalcPa(stcg) : null;
                      const clr = (v) => v >= 0 ? 'var(--green)' : 'var(--red)';
                      const sign = (v) => v >= 0 ? '+' : '';
                      const subCell = (v, pct, dur, pa) => v !== 0 ? (
                        <td style={nw}>
                          <div style={{ fontWeight: 600, color: clr(v), ...nw }}>{sign(v)}{formatINR(v)}</div>
                          <div style={{ fontSize: '11px', color: clr(v), opacity: 0.85, ...nw }}>{sign(pct)}{pct.toFixed(1)}%{dur ? ` ${dur}` : ''}</div>
                          {pa !== null && <div style={{ fontSize: '11px', color: clr(v), opacity: 0.85, ...nw }}>{sign(pa)}{pa.toFixed(1)}% p.a.</div>}
                        </td>
                      ) : <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>;
                      return hasHeld ? (
                        <>
                          {subCell(upl, uplPct, _durationStr, uplPa)}
                          {subCell(ltcg, ltcgPct, _ltcgH.durStr, ltcgPa)}
                          {subCell(stcg, stcgPct, _stcgH.durStr, stcgPa)}
                        </>
                      ) : (
                        <>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                        </>
                      );
                    })()}
                    {/* ── Realized P&L: Total | LTCG | STCG ── */}
                    {col('realizedPL') && (() => {
                      const nw = { whiteSpace: 'nowrap' };
                      const val = stock.realized_pl || 0;
                      const ltcg = stock.ltcg_realized_pl || 0;
                      const stcg = stock.stcg_realized_pl || 0;
                      const show = val !== 0;
                      const rplPct = show ? _pctOfSold(val) : 0;
                      const rplPa = show ? _calcSoldPa(val) : null;
                      const ltcgPct = ltcg !== 0 ? _ltcgSoldPctOf(ltcg) : 0;
                      const ltcgPa = ltcg !== 0 ? _ltcgCalcSoldPa(ltcg) : null;
                      const stcgPct = stcg !== 0 ? _stcgSoldPctOf(stcg) : 0;
                      const stcgPa = stcg !== 0 ? _stcgCalcSoldPa(stcg) : null;
                      const clr = (v) => v >= 0 ? 'var(--green)' : 'var(--red)';
                      const sign = (v) => v >= 0 ? '+' : '';
                      const subCell = (v, qty, pct, dur, pa) => v !== 0 ? (
                        <td style={nw}>
                          <div style={{ fontWeight: 600, color: clr(v), ...nw }}>{sign(v)}{formatINR(v)}</div>
                          {qty > 0 && <div style={{ fontSize: '11px', color: clr(v), opacity: 0.85, ...nw }}>on {qty} units</div>}
                          <div style={{ fontSize: '11px', color: clr(v), opacity: 0.85, ...nw }}>{sign(pct)}{pct.toFixed(1)}%{dur ? ` ${dur}` : ''}</div>
                          {pa !== null && <div style={{ fontSize: '11px', color: clr(v), opacity: 0.85, ...nw }}>{sign(pa)}{pa.toFixed(1)}% p.a.</div>}
                        </td>
                      ) : <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>;
                      return show ? (
                        <>
                          {subCell(val, stock.total_sold_qty, rplPct, _soldDurationStr, rplPa)}
                          {subCell(ltcg, stock.ltcg_sold_qty, ltcgPct, _ltcgSold.durStr, ltcgPa)}
                          {subCell(stcg, stock.stcg_sold_qty, stcgPct, _stcgSold.durStr, stcgPa)}
                        </>
                      ) : (
                        <>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                          <td><span style={{ color: 'var(--text-muted)' }}>-</span></td>
                        </>
                      );
                    })()}
                    {col('dividends') && <td style={{ whiteSpace: 'nowrap' }}>
                      {(stock.total_dividend || 0) > 0 ? (() => {
                        const divPct = _pctOf(stock.total_dividend);
                        const divPa = _calcPa(stock.total_dividend);
                        return (
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--green)', whiteSpace: 'nowrap' }}>
                              +{formatINR(stock.total_dividend)}
                            </div>
                            {(stock.dividend_units || 0) > 0 && (
                              <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85 }}>
                                on {stock.dividend_units} units
                              </div>
                            )}
                            <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85, whiteSpace: 'nowrap' }}>
                              +{divPct.toFixed(1)}%{_durationStr ? ` ${_durationStr}` : ''}
                            </div>
                            {divPa !== null && (
                              <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85, whiteSpace: 'nowrap' }}>
                                +{divPa.toFixed(1)}% p.a.
                              </div>
                            )}
                          </div>
                        );
                      })() : (
                        <span style={{ color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>}
                  </tr>

                  {/* ── Expanded detail row ──────────────────── */}
                  {isExpanded && (
                    <tr>
                      <td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                        <StockDetail
                          stock={stock}
                          portfolio={portfolio}
                          transactions={transactions}
                          onSell={onSell}
                          onAddStock={onAddStock}
                          onDividend={onDividend}
                          selectedLots={selectedLots}
                          onToggleLot={toggleLot}
                          onToggleAllLots={toggleAllLots}
                        />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Floating bulk action bar (lot-level) ──────────── */}
      {selectedCount > 0 && (
        <div style={{
          position: 'sticky',
          bottom: 0,
          left: 0,
          right: 0,
          background: 'var(--bg-card)',
          borderTop: '2px solid var(--blue)',
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          zIndex: 10,
          borderRadius: '0 0 var(--radius-sm) var(--radius-sm)',
          boxShadow: '0 -4px 12px rgba(0,0,0,0.3)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontWeight: 600, fontSize: '14px' }}>
              {selectedCount} lot{selectedCount > 1 ? 's' : ''} selected
              <span style={{ fontWeight: 400, color: 'var(--text-dim)', marginLeft: '8px' }}>
                ({selectedQty} shares)
              </span>
            </span>
            <button
              className="btn btn-ghost btn-sm"
              onClick={clearSelection}
              style={{ fontSize: '12px' }}
            >
              Clear
            </button>
          </div>
          <button
            className="btn btn-danger"
            onClick={handleBulkSell}
            style={{ fontWeight: 600, padding: '8px 24px' }}
          >
            Sell {selectedCount} Lot{selectedCount > 1 ? 's' : ''} ({selectedQty} share{selectedQty !== 1 ? 's' : ''}{selectedPL !== 0 ? `, ${selectedPL >= 0 ? '+' : ''}${formatINR(selectedPL)} (${selectedPLPct >= 0 ? '+' : ''}${selectedPLPct.toFixed(2)}%${selectedPLPa !== null ? `, ${selectedPLPa >= 0 ? '+' : ''}${selectedPLPa.toFixed(1)}% p.a.` : ''})` : ''})
          </button>
        </div>
      )}
    </div>
  );
}
