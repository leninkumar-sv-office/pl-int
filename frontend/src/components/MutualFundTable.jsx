import React, { useState, useRef, useEffect } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

const formatUnits = (u) => {
  if (u === null || u === undefined) return '0';
  return Number(u).toLocaleString('en-IN', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
};

const UPPER_ACRONYMS = ['ETF', 'FOF', 'ELSS', 'NFO', 'SIP', 'SBI', 'ICICI', 'HDFC', 'IDFC', 'PPFAS', 'DSP', 'UTI', 'HSBC', 'NPS'];
const LOWER_WORDS = new Set(['of', 'the', 'and', 'for', 'in', 'on', 'at', 'to', 'a', 'an', 'or', 'nor', 'but', 'so', 'yet', 'as', 'via']);

const extractAMC = (name) => {
  const n = name.toUpperCase();
  if (n.startsWith('ICICI')) return 'ICICI Prudential';
  if (n.startsWith('NIPPON')) return 'Nippon India';
  if (n.startsWith('SBI')) return 'SBI';
  if (n.startsWith('KOTAK')) return 'Kotak';
  if (n.startsWith('HDFC')) return 'HDFC';
  if (n.startsWith('TATA')) return 'Tata';
  if (n.startsWith('RELIANCE')) return 'Reliance / Nippon';
  if (n.startsWith('ADITYA')) return 'Aditya Birla';
  if (n.startsWith('AXIS')) return 'Axis';
  if (n.startsWith('DSP')) return 'DSP';
  if (n.startsWith('UTI')) return 'UTI';
  if (n.startsWith('PPFAS') || n.startsWith('PARAG')) return 'PPFAS';
  if (n.startsWith('MOTILAL')) return 'Motilal Oswal';
  if (n.startsWith('CANARA')) return 'Canara Robeco';
  if (n.startsWith('MIRAE')) return 'Mirae Asset';
  if (n.startsWith('QUANT')) return 'Quant';
  if (n.startsWith('FRANKLIN') || n.startsWith('TEMPLETON')) return 'Franklin Templeton';
  if (n.startsWith('SUNDARAM')) return 'Sundaram';
  if (n.startsWith('INVESCO')) return 'Invesco';
  if (n.startsWith('EDELWEISS')) return 'Edelweiss';
  if (n.startsWith('BANDHAN')) return 'Bandhan';
  if (n.startsWith('HSBC')) return 'HSBC';
  return 'Other';
};

const cleanFundName = (name) => {
  const stripped = name
    .replace(/\s*\(Erstwhile[^)]*\)\s*/i, '')
    .replace(/\s*-?\s*Direct\s*(Plan\s*)?([-–]\s*)?(Growth|Dividend)?\s*(Plan\s*)?(Growth\s*)?(Option)?\.?\s*$/i, '')
    .replace(/\s*Direct\s*(Growth|Dividend)?\.?\s*$/i, '')
    .replace(/\s*-\s*$/, '')
    .trim();
  // Only convert if the name is ALL CAPS (leave mixed-case names like "SBI Conservative..." alone)
  if (!stripped || stripped !== stripped.toUpperCase()) return stripped;
  return stripped
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase())
    .replace(/\b[A-Za-z]+\b/g, word => {
      if (UPPER_ACRONYMS.includes(word.toUpperCase())) return word.toUpperCase();
      if (LOWER_WORDS.has(word.toLowerCase()) && word !== stripped.split(/\s+/)[0]) return word.toLowerCase();
      return word;
    });
};

function durationText(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  const now = new Date();
  const days = Math.floor((now - d) / 86400000);
  if (days < 0) return '';
  const y = Math.floor(days / 365);
  const m = Math.floor((days % 365) / 30);
  if (y > 0 && m > 0) return `${y}y ${m}m`;
  if (y > 0) return `${y}y`;
  if (m > 0) return `${m}m`;
  return `${days}d`;
}

/* ── Main table column definitions ────────────────────── */
const COL_DEFS = [
  { id: 'units',        label: 'Units' },
  { id: 'avgNav',       label: 'Avg NAV' },
  { id: 'currentNav',   label: 'Current NAV' },
  { id: 'currentValue', label: 'Current Value' },
  { id: 'invested',     label: 'Invested' },
  { id: 'unrealizedPL', label: 'Unrealized P&L' },
  { id: 'realizedPL',   label: 'Realized P&L' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'mfVisibleCols_v2';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  const DEFAULT_HIDDEN = ['realizedPL'];
  return new Set(ALL_COL_IDS.filter(id => !DEFAULT_HIDDEN.includes(id)));
}

/* ── Held lots sub-table column definitions ───────────── */
const HELD_COL_DEFS = [
  { id: 'buyDate',    label: 'Buy Date' },
  { id: 'units',      label: 'Units' },
  { id: 'nav',        label: 'Buy NAV' },
  { id: 'currentNav', label: 'Current NAV' },
  { id: 'cost',       label: 'Cost' },
  { id: 'current',    label: 'Current Value' },
  { id: 'pl',         label: 'P&L' },
];
const HELD_COL_LS_KEY = 'mfHeldLotsHiddenCols';

function loadHeldHiddenCols() {
  try {
    const saved = localStorage.getItem(HELD_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set();
}

/* ── Held lots sub-table styles (matching stock) ──────── */
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

/* ── 52W Range Bar ──────────────────────────────────── */
function NavRangeBar({ low, high, current, avg }) {
  if (!low || !high || low >= high) {
    return <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>;
  }
  const range = high - low;
  const currentPos = Math.max(0, Math.min(100, ((current - low) / range) * 100));
  const avgPos = Math.max(0, Math.min(100, ((avg - low) / range) * 100));
  return (
    <div className="range-bar-container">
      <div className="range-bar">
        <div className="range-bar-fill" style={{ width: '100%' }} />
        <div className="range-marker buy" style={{ left: `${avgPos}%` }} title={`Avg NAV: ${formatINR(avg)}`} />
        <div className="range-marker current" style={{ left: `${currentPos}%` }} title={`Current: ${formatINR(current)}`} />
      </div>
      <div className="range-labels">
        <span>{formatINR(low)}</span>
        <span>{formatINR(high)}</span>
      </div>
    </div>
  );
}

/* ── Expanded Fund Detail (matches StockDetail) ─────── */
function FundDetail({ fund, onBuyMF, onRedeemMF, onConfigSIP, getSIPForFund, selectedLots, onToggleLot, onToggleAllLots }) {
  const f = fund;
  const heldLots = (f.held_lots || []).slice().sort((a, b) => (b.buy_date || '').localeCompare(a.buy_date || ''));
  const soldLots = (f.sold_lots || []).slice().sort((a, b) => (b.sell_date || '').localeCompare(a.sell_date || ''));
  const currentNav = f.current_nav || 0;

  const allLotsSelected = heldLots.length > 0 && heldLots.every(l => selectedLots.has(l.id));
  const someLotsSelected = heldLots.some(l => selectedLots.has(l.id));

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

  useEffect(() => {
    if (!showColPicker) return;
    const handler = (e) => { if (colPickerRef.current && !colPickerRef.current.contains(e.target)) setShowColPicker(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showColPicker]);

  const totalSoldUnits = soldLots.reduce((sum, s) => sum + (s.units || 0), 0);
  const totalSoldPL = soldLots.reduce((sum, s) => sum + (s.realized_pl || 0), 0);
  const totalSoldCost = soldLots.reduce((sum, s) => sum + ((s.buy_nav || 0) * (s.units || 0)), 0);
  const totalSoldPLPct = totalSoldCost > 0 ? (totalSoldPL / totalSoldCost * 100) : 0;
  const totalSoldWeightedDays = soldLots.reduce((sum, s) => {
    const cost = (s.buy_nav || 0) * (s.units || 0);
    if (cost <= 0 || !s.buy_date || !s.sell_date) return sum;
    const days = Math.floor((new Date(s.sell_date + 'T00:00:00') - new Date(s.buy_date + 'T00:00:00')) / (1000 * 60 * 60 * 24));
    return sum + cost * Math.max(days, 1);
  }, 0);
  const avgSoldDays = totalSoldCost > 0 ? totalSoldWeightedDays / totalSoldCost : 0;
  const totalSoldPLPa = avgSoldDays > 0 && totalSoldCost > 0
    ? (Math.pow(1 + totalSoldPL / totalSoldCost, 365 / avgSoldDays) - 1) * 100
    : null;
  const fundShortName = cleanFundName(f.name);

  return (
    <div style={{
      background: 'var(--bg)',
      borderTop: '1px solid var(--border)',
      padding: '20px 24px',
    }}>
      {/* Action buttons */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        {heldLots.length > 0 && (
          <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>
            Quick actions:
          </span>
        )}
        {onBuyMF && (
          <button
            className="btn btn-primary"
            onClick={(e) => { e.stopPropagation(); onBuyMF({ fund_code: f.fund_code, name: f.name, fund_name: f.name }); }}
            style={{ fontWeight: 600 }}
          >
            + Buy {fundShortName.substring(0, 25)}
          </button>
        )}
        {onConfigSIP && (
          <button
            className="btn btn-ghost"
            onClick={(e) => { e.stopPropagation(); onConfigSIP(f); }}
            style={{ fontWeight: 600 }}
          >
            {getSIPForFund(f.fund_code) ? 'Edit SIP' : 'Setup SIP'}
          </button>
        )}
      </div>

      {/* Stats bar */}
      {currentNav > 0 && (
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
          {(f.week_52_low > 0 || f.week_52_high > 0) && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>52-Week Range</div>
              <NavRangeBar low={f.week_52_low} high={f.week_52_high} current={currentNav} avg={f.avg_nav} />
            </div>
          )}
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Invested</div>
            <div style={{ fontWeight: 600 }}>{formatINR(f.total_invested)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Value</div>
            <div style={{ fontWeight: 600 }}>{formatINR(f.current_value)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Unrealized P&L</div>
            <div style={{ fontWeight: 600, color: f.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {f.unrealized_pl >= 0 ? '+' : ''}{formatINR(f.unrealized_pl)}
            </div>
          </div>
          {f.realized_pl !== 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Realized P&L</div>
              <div style={{ fontWeight: 600, color: f.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {f.realized_pl >= 0 ? '+' : ''}{formatINR(f.realized_pl)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Held Lots sub-table ──────────────────────── */}
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
                      onChange={() => onToggleAllLots(heldLots.map(l => l.id))}
                      style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
                      title="Select all lots for bulk redeem"
                    />
                  </th>
                  {hCol('buyDate')    && <th style={heldTh}>Buy Date</th>}
                  {hCol('units')      && <th style={heldTh}>Units</th>}
                  {hCol('nav')        && <th style={heldTh}>Buy NAV</th>}
                  {hCol('currentNav') && <th style={heldTh}>Current NAV</th>}
                  {hCol('cost')       && <th style={heldTh}>Cost</th>}
                  {hCol('current')    && <th style={heldTh}>Current Value</th>}
                  {hCol('pl')         && <th style={heldTh}>P&L</th>}
                  <th style={heldTh}>Action</th>
                </tr>
              </thead>
              <tbody>
                {heldLots.map((lot, i) => {
                  const isChecked = selectedLots.has(lot.id);
                  const inProfit = lot.pl >= 0;
                  const isLTCG = lot.is_ltcg;
                  const ltcgColor = 'rgba(34,197,94,0.12)';
                  const stcgColor = 'rgba(251,191,36,0.10)';
                  const ltcgBorder = '#22c55e';
                  const stcgBorder = '#f59e0b';
                  return (
                    <tr
                      key={lot.id || i}
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
                          onChange={() => onToggleLot(lot.id)}
                          style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
                        />
                      </td>
                      {hCol('buyDate') && (
                        <td style={heldTd}>
                          <div>{formatDate(lot.buy_date)}</div>
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
                          <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 4 }}>
                            {durationText(lot.buy_date)}
                          </span>
                        </td>
                      )}
                      {hCol('units')   && <td style={{ ...heldTd, fontWeight: 600 }}>{formatUnits(lot.units)}</td>}
                      {hCol('nav')     && <td style={heldTd}>{formatINR(lot.buy_price)}</td>}
                      {hCol('currentNav') && (
                        <td style={{ ...heldTd, fontWeight: 600, color: currentNav > 0 && currentNav >= lot.buy_price ? 'var(--green)' : 'var(--red)' }}>
                          {currentNav > 0 ? formatINR(currentNav) : '--'}
                        </td>
                      )}
                      {hCol('cost')    && <td style={heldTd}>{formatINR(lot.buy_cost)}</td>}
                      {hCol('current') && (
                        <td style={{ ...heldTd, color: inProfit ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                          {currentNav > 0 ? formatINR(lot.current_value) : '--'}
                        </td>
                      )}
                      {hCol('pl') && (() => {
                        const mfDays = lot.buy_date ? Math.floor((Date.now() - new Date(lot.buy_date).getTime()) / 86400000) : 0;
                        const mfCost = lot.buy_cost || (lot.buy_price * lot.units) || 0;
                        const mfPa = mfDays > 0 && mfCost > 0
                          ? (Math.pow(1 + lot.pl / mfCost, 365 / mfDays) - 1) * 100 : null;
                        const clr = inProfit ? 'var(--green)' : 'var(--red)';
                        return (
                        <td style={heldTd}>
                          {currentNav > 0 ? (
                            <div>
                              <div style={{ fontWeight: 600, color: clr }}>{inProfit ? '+' : ''}{formatINR(lot.pl)}</div>
                              <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                {lot.pl_pct >= 0 ? '+' : ''}{lot.pl_pct?.toFixed(2)}%
                              </div>
                              {mfPa !== null && (
                                <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                                  {mfPa >= 0 ? '+' : ''}{mfPa.toFixed(2)}% p.a.
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
                          onClick={(e) => { e.stopPropagation(); onRedeemMF({ ...f, preSelectedUnits: lot.units }); }}
                          style={{ minWidth: '56px', padding: '4px 10px' }}
                        >
                          Redeem
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

      {/* ── Redeemed (Sold) Lots sub-table ────────────── */}
      {soldLots.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <span>Redemptions ({soldLots.length})</span>
            <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-dim)' }}>
              {formatUnits(totalSoldUnits)} units
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
                  <th style={heldTh}>Units</th>
                  <th style={heldTh}>Buy NAV</th>
                  <th style={heldTh}>Sell NAV</th>
                  <th style={heldTh}>Cost</th>
                  <th style={heldTh}>Sale Value</th>
                  <th style={heldTh}>Realized P&L</th>
                </tr>
              </thead>
              <tbody>
                {soldLots.map((s, i) => (
                  <tr key={s.id || i} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={heldTd}>{formatDate(s.buy_date)}</td>
                    <td style={heldTd}>{formatDate(s.sell_date)}</td>
                    <td style={{ ...heldTd, fontWeight: 600 }}>{formatUnits(s.units)}</td>
                    <td style={heldTd}>{formatINR(s.buy_nav)}</td>
                    <td style={heldTd}>{formatINR(s.sell_nav)}</td>
                    <td style={heldTd}>{formatINR((s.buy_nav || 0) * (s.units || 0))}</td>
                    <td style={{ ...heldTd, fontWeight: 600 }}>{formatINR((s.sell_nav || 0) * (s.units || 0))}</td>
                    {(() => {
                      const mfsCost = (s.buy_nav || 0) * (s.units || 0);
                      const mfsPct = mfsCost > 0 ? (s.realized_pl / mfsCost * 100) : 0;
                      const mfsDays = s.buy_date && s.sell_date
                        ? Math.floor((new Date(s.sell_date + 'T00:00:00') - new Date(s.buy_date + 'T00:00:00')) / 86400000) : 0;
                      const mfsPa = mfsDays > 0 && mfsCost > 0
                        ? (Math.pow(1 + s.realized_pl / mfsCost, 365 / mfsDays) - 1) * 100 : null;
                      const clr = s.realized_pl >= 0 ? 'var(--green)' : 'var(--red)';
                      const sign = s.realized_pl >= 0 ? '+' : '';
                      return (
                    <td style={heldTd}>
                      <div>
                        <div style={{ fontWeight: 600, color: clr }}>{sign}{formatINR(s.realized_pl)}</div>
                        {mfsCost > 0 && (
                          <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                            {sign}{mfsPct.toFixed(2)}%
                          </div>
                        )}
                        {mfsPa !== null && (
                          <div style={{ fontSize: '11px', color: clr, opacity: 0.85 }}>
                            {mfsPa >= 0 ? '+' : ''}{mfsPa.toFixed(2)}% p.a.
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

      {/* LTCG/STCG summary */}
      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
        <div style={{ padding: '8px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--green)', fontWeight: 600, letterSpacing: '0.4px' }}>LTCG (Unrealized)</div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: f.ltcg_unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {f.ltcg_unrealized_pl >= 0 ? '+' : ''}{formatINR(f.ltcg_unrealized_pl)}
          </div>
        </div>
        <div style={{ padding: '8px 12px', background: 'rgba(245,158,11,0.06)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.15)' }}>
          <div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#f59e0b', fontWeight: 600, letterSpacing: '0.4px' }}>STCG (Unrealized)</div>
          <div style={{ fontSize: '14px', fontWeight: 600, color: f.stcg_unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {f.stcg_unrealized_pl >= 0 ? '+' : ''}{formatINR(f.stcg_unrealized_pl)}
          </div>
        </div>
        {(f.ltcg_realized_pl !== 0 || f.stcg_realized_pl !== 0) && (
          <>
            <div style={{ padding: '8px 12px', background: 'rgba(99,102,241,0.06)', borderRadius: 6, border: '1px solid rgba(99,102,241,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#6366f1', fontWeight: 600, letterSpacing: '0.4px' }}>LTCG (Realized)</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: f.ltcg_realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {f.ltcg_realized_pl >= 0 ? '+' : ''}{formatINR(f.ltcg_realized_pl)}
              </div>
            </div>
            <div style={{ padding: '8px 12px', background: 'rgba(99,102,241,0.06)', borderRadius: 6, border: '1px solid rgba(99,102,241,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#6366f1', fontWeight: 600, letterSpacing: '0.4px' }}>STCG (Realized)</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: f.stcg_realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {f.stcg_realized_pl >= 0 ? '+' : ''}{formatINR(f.stcg_realized_pl)}
              </div>
            </div>
          </>
        )}
      </div>

      {heldLots.length === 0 && soldLots.length === 0 && (
        <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
          No lot or transaction details available.
        </div>
      )}
    </div>
  );
}


/* ── Main Table ───────────────────────────────────────── */
export default function MutualFundTable({ funds, loading, mfDashboard, onBuyMF, onRedeemMF, onConfigSIP, sipConfigs, onImportCDSLCAS }) {
  const [expandedFund, setExpandedFund] = useState(null);
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const casFileInputRef = useRef(null);
  const [casImporting, setCasImporting] = useState(false);
  const [visibleCols, setVisibleCols] = useState(loadVisibleCols);
  const [colPickerOpen, setColPickerOpen] = useState(false);
  const colPickerRef = useRef(null);
  const [searchTerm, setSearchTerm] = useState('');
  const searchRef = useRef(null);
  const [heldOnly, setHeldOnly] = useState(true);

  // ── Lot-level selection for bulk redeem ──
  const [selectedLots, setSelectedLots] = useState(new Set());

  // Clear lot selection when collapsing / switching fund
  const prevExpanded = useRef(null);
  useEffect(() => {
    if (prevExpanded.current !== expandedFund) {
      setSelectedLots(new Set());
      prevExpanded.current = expandedFund;
    }
  }, [expandedFund]);

  const toggleLot = (lotId) => {
    setSelectedLots(prev => {
      const next = new Set(prev);
      if (next.has(lotId)) next.delete(lotId); else next.add(lotId);
      return next;
    });
  };

  const toggleAllLots = (lotIds) => {
    setSelectedLots(prev => {
      const allSelected = lotIds.every(id => prev.has(id));
      const next = new Set(prev);
      if (allSelected) lotIds.forEach(id => next.delete(id));
      else lotIds.forEach(id => next.add(id));
      return next;
    });
  };

  const clearSelection = () => setSelectedLots(new Set());

  const getSIPForFund = (fund_code) => (sipConfigs || []).find(s => s.fund_code === fund_code);

  const col = (id) => visibleCols.has(id);

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

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };

  const SortIcon = ({ field }) => {
    if (sortKey !== field) return <span style={{ opacity: 0.3, fontSize: '10px' }}> &updownarrow;</span>;
    return <span style={{ fontSize: '10px' }}> {sortDir === 'asc' ? '\u2191' : '\u2193'}</span>;
  };

  // Filter + sort
  const q = searchTerm.trim().toLowerCase();
  let filtered = (funds || []).filter(f => {
    if (heldOnly && f.total_held_units <= 0) return false;
    if (q) {
      return f.name.toLowerCase().includes(q) || f.fund_code.toLowerCase().includes(q);
    }
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'name':         va = a.name; vb = b.name; break;
      case 'units':        va = a.total_held_units; vb = b.total_held_units; break;
      case 'avgNav':       va = a.avg_nav; vb = b.avg_nav; break;
      case 'invested':     va = a.total_invested; vb = b.total_invested; break;
      case 'currentNav':   va = a.current_nav; vb = b.current_nav; break;
      case 'currentValue': va = a.current_value; vb = b.current_value; break;
      case 'unrealizedPL': va = a.unrealized_pl; vb = b.unrealized_pl; break;
      case 'realizedPL':   va = a.realized_pl; vb = b.realized_pl; break;
      default:             va = a.name; vb = b.name;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  // Group by AMC for visual rendering (preserving sort order)
  const amcOrder = [];
  const amcFundsMap = {};
  for (const f of filtered) {
    const amc = extractAMC(f.name);
    if (!amcFundsMap[amc]) {
      amcOrder.push(amc);
      amcFundsMap[amc] = [];
    }
    amcFundsMap[amc].push(f);
  }

  // Stats
  const fundsWithHeld = (funds || []).filter(f => f.total_held_units > 0);
  const totalHeldFunds = fundsWithHeld.length;
  const inProfit = fundsWithHeld.filter(f => f.unrealized_pl >= 0).length;
  const inLoss = fundsWithHeld.filter(f => f.unrealized_pl < 0).length;

  // Dynamic column count: 2 always-on (expand + name) + visible cols
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  // Count selected lots info for the action bar
  const selectedCount = selectedLots.size;
  const expandedFundData = selectedCount > 0 ? filtered.find(f => f.fund_code === expandedFund) : null;
  const selectedItems = expandedFundData?.held_lots?.filter(l => selectedLots.has(l.id)) || [];
  const selectedUnits = selectedItems.reduce((sum, l) => sum + l.units, 0);
  const selectedPL = selectedItems.reduce((sum, l) => sum + (l.pl || 0), 0);
  const selectedCost = selectedItems.reduce((sum, l) => sum + (l.buy_cost || (l.buy_price * l.units) || 0), 0);
  const selectedPLPct = selectedCost > 0 ? (selectedPL / selectedCost * 100) : 0;

  if (loading && (funds || []).length === 0) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading mutual fund data...
      </div>
    );
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Mutual Fund Summary</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">
            {totalHeldFunds} funds held
          </span>
          <span className="section-badge" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
            {inProfit} in profit
          </span>
          <span className="section-badge" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
            {inLoss} in loss
          </span>
          {/* CDSL CAS PDF Import Button */}
          <input
            ref={casFileInputRef}
            type="file"
            accept=".pdf"
            multiple
            onChange={async (e) => {
              const files = Array.from(e.target.files || []);
              if (files.length === 0 || !onImportCDSLCAS) return;
              e.target.value = '';
              const pdfFiles = files.filter(f => f.name.toLowerCase().endsWith('.pdf'));
              if (pdfFiles.length === 0) return;
              setCasImporting(true);
              try {
                await onImportCDSLCAS(pdfFiles);
              } catch (err) {
                // Error handled in parent
              } finally {
                setCasImporting(false);
              }
            }}
            style={{ display: 'none' }}
          />
          <button
            onClick={() => casFileInputRef.current?.click()}
            disabled={casImporting}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              background: casImporting ? 'var(--bg-input)' : 'var(--blue)',
              color: casImporting ? 'var(--text-muted)' : '#fff',
              border: 'none',
              borderRadius: 'var(--radius-sm)',
              cursor: casImporting ? 'wait' : 'pointer',
              whiteSpace: 'nowrap',
              opacity: casImporting ? 0.7 : 1,
            }}
            title="Import transactions from CDSL CAS statement PDF (all AMCs)"
          >
            {casImporting ? 'Parsing CAS...' : 'Import CDSL CAS'}
          </button>
        </div>
      </div>

      {/* ── MF Summary Bar (matches Stock Summary Bar) ── */}
      {mfDashboard && (() => {
        const uplPct = mfDashboard.total_invested > 0 ? (mfDashboard.unrealized_pl / mfDashboard.total_invested) * 100 : 0;
        return (
          <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Invested</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(mfDashboard.total_invested)}</div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Value</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(mfDashboard.current_value)}</div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Unrealized P&L</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: mfDashboard.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {mfDashboard.unrealized_pl >= 0 ? '+' : ''}{formatINR(mfDashboard.unrealized_pl)}
                <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4 }}>
                  ({uplPct >= 0 ? '+' : ''}{uplPct.toFixed(2)}%)
                </span>
              </div>
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Realized P&L</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: mfDashboard.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {mfDashboard.realized_pl >= 0 ? '+' : ''}{formatINR(mfDashboard.realized_pl)}
              </div>
            </div>
            <div style={{ flex: '1 1 80px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Funds</div>
              <div style={{ fontSize: '16px', fontWeight: 600 }}>
                {totalHeldFunds}
                <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4, color: 'var(--text-muted)' }}>
                  ({inProfit}&uarr; {inLoss}&darr;)
                </span>
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Search bar (matches stock search) ──────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef}
            type="text"
            placeholder="Search funds by name or code..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
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
          {searchTerm && (
            <span
              onClick={() => { setSearchTerm(''); if (searchRef.current) searchRef.current.focus(); }}
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
            checked={heldOnly}
            onChange={(e) => setHeldOnly(e.target.checked)}
            style={{ cursor: 'pointer', accentColor: 'var(--blue)' }}
          />
          Held only
        </label>
        {(q || heldOnly) && (
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {filtered.length} of {(funds || []).length} funds
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
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Main Table ───────────────────────────────── */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th style={{ width: '28px' }}></th>
              <th onClick={() => handleSort('name')} style={{ cursor: 'pointer' }}>
                Fund<SortIcon field="name" />
              </th>
              {col('units') && <th onClick={() => handleSort('units')} style={{ cursor: 'pointer' }}>
                Units<SortIcon field="units" />
              </th>}
              {col('avgNav') && <th onClick={() => handleSort('avgNav')} style={{ cursor: 'pointer' }}>
                Avg NAV<SortIcon field="avgNav" />
              </th>}
              {col('currentNav') && <th onClick={() => handleSort('currentNav')} style={{ cursor: 'pointer' }}>
                Current NAV<SortIcon field="currentNav" />
              </th>}
              {col('currentValue') && <th onClick={() => handleSort('currentValue')} style={{ cursor: 'pointer' }}>
                Current Value<SortIcon field="currentValue" />
              </th>}
              {col('invested') && <th onClick={() => handleSort('invested')} style={{ cursor: 'pointer' }}>
                Invested<SortIcon field="invested" />
              </th>}
              {col('unrealizedPL') && <th onClick={() => handleSort('unrealizedPL')} style={{ cursor: 'pointer' }}>
                Unrealized P&L<SortIcon field="unrealizedPL" />
              </th>}
              {col('realizedPL') && <th onClick={() => handleSort('realizedPL')} style={{ cursor: 'pointer' }}>
                Realized P&L<SortIcon field="realizedPL" />
              </th>}
            </tr>
          </thead>
          <tbody>
            {amcOrder.map((amc, amcIdx) => {
              const amcFunds = amcFundsMap[amc];
              const showHeader = amcFunds.length > 1;
              return (
                <React.Fragment key={amc}>
                  {showHeader && (
                    <tr>
                      <td colSpan={TOTAL_COLS} style={{
                        padding: amcIdx === 0 ? '10px 16px 6px' : '18px 16px 6px',
                        fontSize: '12px',
                        fontWeight: 700,
                        color: 'var(--text-dim)',
                        letterSpacing: '0.6px',
                        textTransform: 'uppercase',
                        borderBottom: '1px solid var(--border)',
                        background: 'rgba(255,255,255,0.02)',
                      }}>
                        <span style={{ borderLeft: '3px solid var(--blue)', paddingLeft: 10 }}>
                          {amc}
                        </span>
                        <span style={{ fontWeight: 400, marginLeft: 8, fontSize: '11px', color: 'var(--text-muted)' }}>
                          {amcFunds.length} funds
                        </span>
                      </td>
                    </tr>
                  )}
                  {amcFunds.map(f => {
              const isExpanded = expandedFund === f.fund_code;
              const hasHeld = f.total_held_units > 0;
              const plColor = f.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)';
              const rplColor = f.realized_pl >= 0 ? 'var(--green)' : 'var(--red)';
              const sipCfg = getSIPForFund(f.fund_code);

              return (
                <React.Fragment key={f.fund_code}>
                  <tr
                    className={f.is_above_avg_nav && hasHeld ? 'highlight-profit' : ''}
                    style={{
                      opacity: hasHeld ? 1 : 0.6,
                      cursor: 'pointer',
                      background: isExpanded ? 'var(--bg-card-hover)' : undefined,
                    }}
                    onClick={() => setExpandedFund(isExpanded ? null : f.fund_code)}
                  >
                    <td style={{ padding: '14px 4px 14px 16px', width: '28px', fontSize: '14px', color: 'var(--text-dim)' }}>
                      {isExpanded ? '\u25BE' : '\u25B8'}
                    </td>
                    <td>
                      <div className="stock-symbol">
                        {cleanFundName(f.name)}
                        {sipCfg && sipCfg.enabled && (
                          <span style={{ marginLeft: 6, padding: '1px 5px', borderRadius: 3, background: 'rgba(0,210,106,0.12)', color: 'var(--green)', fontSize: '10px', fontWeight: 600 }}>
                            SIP
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '10px', color: 'var(--text-muted)', opacity: 0.5, marginTop: '1px' }}>
                        Direct Growth
                      </div>
                      <div className="stock-name">
                        {f.num_held_lots} lot{f.num_held_lots !== 1 ? 's' : ''}
                        {f.num_sold_lots > 0 && <span> &bull; {f.num_sold_lots} redeemed</span>}
                      </div>
                    </td>
                    {col('units') && <td>
                      <div style={{ fontWeight: 700, fontSize: '15px' }}>
                        {hasHeld ? formatUnits(f.total_held_units) : '-'}
                      </div>
                      {f.num_held_lots > 1 && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          {f.num_held_lots} lots
                        </div>
                      )}
                    </td>}
                    {col('avgNav') && <td>{hasHeld ? formatINR(f.avg_nav) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>}
                    {col('currentNav') && <td>
                      {f.current_nav > 0 ? (
                        <div>
                          <div style={{
                            fontWeight: 600,
                            color: hasHeld ? (f.is_above_avg_nav ? 'var(--green)' : 'var(--red)') : 'var(--text)',
                          }}>
                            {formatINR(f.current_nav)}
                          </div>
                          {(f.day_change_pct || 0) !== 0 && (
                            <div style={{ fontSize: '10px', color: f.day_change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              1D: {f.day_change_pct >= 0 ? '+' : ''}{f.day_change_pct.toFixed(2)}%
                            </div>
                          )}
                          {f.week_change_pct !== 0 && (
                            <div style={{ fontSize: '10px', color: f.week_change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              7D: {f.week_change_pct >= 0 ? '+' : ''}{f.week_change_pct.toFixed(2)}%
                            </div>
                          )}
                          {f.month_change_pct !== 0 && (
                            <div style={{ fontSize: '10px', color: f.month_change_pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
                              1M: {f.month_change_pct >= 0 ? '+' : ''}{f.month_change_pct.toFixed(2)}%
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>--</span>
                      )}
                    </td>}
                    {col('currentValue') && <td>
                      <div style={{ fontWeight: 600 }}>
                        {hasHeld ? formatINR(f.current_value) : <span style={{ color: 'var(--text-muted)' }}>-</span>}
                      </div>
                    </td>}
                    {col('invested') && <td>{hasHeld ? formatINR(f.total_invested) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>}
                    {col('unrealizedPL') && (() => {
                      const lots = f.held_lots || [];
                      const totalCost = f.total_invested || 0;
                      const weightedDays = lots.reduce((sum, l) => {
                        const cost = l.buy_cost || (l.buy_price * l.units) || 0;
                        if (cost <= 0 || !l.buy_date) return sum;
                        const days = Math.floor((Date.now() - new Date(l.buy_date + 'T00:00:00').getTime()) / 86400000);
                        return sum + cost * days;
                      }, 0);
                      const avgDays = totalCost > 0 ? Math.round(weightedDays / totalCost) : 0;
                      const pa = avgDays > 0 && totalCost > 0
                        ? (Math.pow(1 + f.unrealized_pl / totalCost, 365 / avgDays) - 1) * 100 : null;
                      const durY = Math.floor(avgDays / 365);
                      const durM = Math.floor((avgDays % 365) / 30);
                      const durD = avgDays % 30;
                      let durStr = '';
                      if (durY > 0) durStr += `${durY}y `;
                      if (durM > 0) durStr += `${durM}m `;
                      if (durD > 0 && durY === 0) durStr += `${durD}d`;
                      durStr = durStr.trim();
                      return (
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {hasHeld && f.unrealized_pl !== 0 ? (
                        <div>
                          <div style={{ fontWeight: 600, color: plColor }}>
                            {f.unrealized_pl >= 0 ? '+' : ''}{formatINR(f.unrealized_pl)}
                          </div>
                          <div style={{ fontSize: '11px', color: plColor, opacity: 0.85 }}>
                            {f.unrealized_pl_pct >= 0 ? '+' : ''}{f.unrealized_pl_pct?.toFixed(2)}%
                            {durStr ? ` in ${durStr}` : ''}
                          </div>
                          {pa !== null && (
                            <div style={{ fontSize: '11px', color: plColor, opacity: 0.85 }}>
                              {pa >= 0 ? '+' : ''}{pa.toFixed(1)}% p.a.
                            </div>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>);
                    })()}
                    {col('realizedPL') && <td style={{ whiteSpace: 'nowrap' }}>
                      {f.realized_pl !== 0 ? (
                        <div style={{ fontWeight: 600, color: rplColor }}>
                          {f.realized_pl >= 0 ? '+' : ''}{formatINR(f.realized_pl)}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>}
                  </tr>

                  {/* ── Expanded detail row ────────────────── */}
                  {isExpanded && (
                    <tr>
                      <td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                        <FundDetail
                          fund={f}
                          onBuyMF={onBuyMF}
                          onRedeemMF={onRedeemMF}
                          onConfigSIP={onConfigSIP}
                          getSIPForFund={getSIPForFund}
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
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Floating bulk action bar (lot-level) ──────── */}
      {selectedCount > 0 && selectedItems.length > 0 && (
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
              {selectedItems.length} lot{selectedItems.length > 1 ? 's' : ''} selected
              <span style={{ fontWeight: 400, color: 'var(--text-dim)', marginLeft: '8px' }}>
                ({formatUnits(selectedUnits)} units)
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
            onClick={() => {
              if (onRedeemMF && expandedFundData) {
                onRedeemMF({ ...expandedFundData, preSelectedUnits: selectedUnits });
              }
            }}
            style={{ fontWeight: 600, padding: '8px 24px' }}
          >
            Redeem {selectedItems.length} Lot{selectedItems.length > 1 ? 's' : ''} ({formatUnits(selectedUnits)} units{selectedPL !== 0 ? `, ${selectedPL >= 0 ? '+' : ''}${formatINR(selectedPL)} (${selectedPLPct >= 0 ? '+' : ''}${selectedPLPct.toFixed(2)}%)` : ''})
          </button>
        </div>
      )}
    </div>
  );
}
