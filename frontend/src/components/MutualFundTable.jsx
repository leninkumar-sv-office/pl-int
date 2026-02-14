import React, { useState } from 'react';

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

/* Duration text */
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

/* ── Column definitions ────────────────────────────── */
const COL_DEFS = [
  { id: 'name',         label: 'Fund Name' },
  { id: 'units',        label: 'Units' },
  { id: 'avgNav',       label: 'Avg NAV' },
  { id: 'invested',     label: 'Invested' },
  { id: 'currentNav',   label: 'Current NAV' },
  { id: 'currentValue', label: 'Current Value' },
  { id: 'unrealizedPL', label: 'Unrealized P&L' },
  { id: 'realizedPL',   label: 'Realized P&L' },
  { id: '52w',          label: '52W Range' },
];
const DEFAULT_HIDDEN = ['realizedPL', '52w'];
const LS_KEY = 'mfVisibleCols_v1';

function loadHiddenCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(DEFAULT_HIDDEN);
}

/* ── 52W Range Bar ──────────────────────────────────── */
function NavRangeBar({ low, high, current, avg }) {
  if (!low || !high || low >= high) {
    return <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>;
  }
  const range = high - low;
  const currentPos = Math.max(0, Math.min(100, ((current - low) / range) * 100));
  const avgPos = Math.max(0, Math.min(100, ((avg - low) / range) * 100));
  return (
    <div style={{ minWidth: 120 }}>
      <div style={{ position: 'relative', height: 6, background: 'var(--bg-hover)', borderRadius: 3 }}>
        <div style={{ position: 'absolute', left: `${avgPos}%`, top: -2, width: 2, height: 10, background: '#f59e0b', borderRadius: 1 }}
             title={`Avg NAV: ${formatINR(avg)}`} />
        <div style={{ position: 'absolute', left: `${currentPos}%`, top: -3, width: 8, height: 12, background: 'var(--green)', borderRadius: '50%', transform: 'translateX(-4px)' }}
             title={`Current: ${formatINR(current)}`} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
        <span>{formatINR(low)}</span>
        <span>{formatINR(high)}</span>
      </div>
    </div>
  );
}


export default function MutualFundTable({ funds, loading, mfDashboard, onBuyMF, onRedeemMF, onConfigSIP, sipConfigs }) {
  const [expandedFund, setExpandedFund] = useState(null);
  const [sortKey, setSortKey] = useState('name');
  const [sortDir, setSortDir] = useState('asc');
  const [hiddenCols, setHiddenCols] = useState(loadHiddenCols);
  const [showColPicker, setShowColPicker] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [heldOnly, setHeldOnly] = useState(true);

  // Helper: look up SIP config for a fund
  const getSIPForFund = (fund_code) => (sipConfigs || []).find(s => s.fund_code === fund_code);

  const isCol = (id) => !hiddenCols.has(id);

  const toggleCol = (id) => {
    setHiddenCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      localStorage.setItem(LS_KEY, JSON.stringify([...next]));
      return next;
    });
  };

  const handleSort = (key) => {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  };
  const arrow = (key) => sortKey === key ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ' ↕';

  // Filter + sort
  let filtered = (funds || []).filter(f => {
    if (heldOnly && f.total_held_units <= 0) return false;
    if (searchTerm) {
      const q = searchTerm.toLowerCase();
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

  // Totals
  const totalInvested = filtered.reduce((s, f) => s + f.total_invested, 0);
  const totalValue = filtered.reduce((s, f) => s + f.current_value, 0);
  const totalUPL = filtered.reduce((s, f) => s + f.unrealized_pl, 0);
  const totalRPL = filtered.reduce((s, f) => s + f.realized_pl, 0);

  const thStyle = { padding: '8px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, borderBottom: '2px solid var(--border)', cursor: 'pointer', whiteSpace: 'nowrap', userSelect: 'none' };
  const tdStyle = { padding: '10px 12px', fontSize: '13px', borderBottom: '1px solid var(--border)', verticalAlign: 'middle' };

  /* Sub-table styles (compact) */
  const subTh = { padding: '5px 8px', textAlign: 'left', fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text-dim)', fontWeight: 600, borderBottom: '1px solid var(--border)' };
  const subTd = { padding: '5px 8px', fontSize: '12px', verticalAlign: 'middle' };

  return (
    <div className="card" style={{ marginBottom: '16px' }}>
      {/* ── MF Dashboard Summary ─────────────────────── */}
      {mfDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Invested</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(mfDashboard.total_invested)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Value</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(mfDashboard.current_value)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Unrealized P&L</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: mfDashboard.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {mfDashboard.unrealized_pl >= 0 ? '+' : ''}{formatINR(mfDashboard.unrealized_pl)}
              <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4 }}>
                ({mfDashboard.unrealized_pl_pct >= 0 ? '+' : ''}{mfDashboard.unrealized_pl_pct?.toFixed(2)}%)
              </span>
            </div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Realized P&L</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: mfDashboard.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {mfDashboard.realized_pl >= 0 ? '+' : ''}{formatINR(mfDashboard.realized_pl)}
            </div>
          </div>
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Funds</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>
              {mfDashboard.total_funds}
              <span style={{ fontSize: '12px', fontWeight: 400, marginLeft: 4, color: 'var(--text-muted)' }}>
                ({mfDashboard.funds_in_profit}↑ {mfDashboard.funds_in_loss}↓)
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Toolbar ──────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 16px', borderBottom: '1px solid var(--border)', flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 600, whiteSpace: 'nowrap' }}>
          Mutual Funds ({filtered.length})
        </h3>

        {/* Column picker */}
        <div style={{ position: 'relative' }}>
          <button
            onClick={() => setShowColPicker(p => !p)}
            style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', borderRadius: 4, padding: '3px 8px', fontSize: '11px', color: 'var(--text-dim)', cursor: 'pointer' }}
          >
            Columns ▾
          </button>
          {showColPicker && (
            <div style={{ position: 'absolute', top: '100%', left: 0, zIndex: 999, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 6, padding: 8, minWidth: 160, boxShadow: '0 4px 12px rgba(0,0,0,0.3)' }}>
              {COL_DEFS.filter(c => c.id !== 'name').map(c => (
                <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '3px 4px', fontSize: '12px', cursor: 'pointer', color: 'var(--text-dim)' }}>
                  <input type="checkbox" checked={isCol(c.id)} onChange={() => toggleCol(c.id)} style={{ accentColor: 'var(--green)' }} />
                  {c.label}
                </label>
              ))}
            </div>
          )}
        </div>

        <div style={{ flex: 1 }} />

        {/* Search */}
        <input
          type="text"
          placeholder="Search funds..."
          value={searchTerm}
          onChange={e => setSearchTerm(e.target.value)}
          style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', borderRadius: 6, padding: '5px 10px', fontSize: '12px', color: 'var(--text)', width: 180 }}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '12px', color: 'var(--text-dim)', cursor: 'pointer' }}>
          <input type="checkbox" checked={heldOnly} onChange={() => setHeldOnly(p => !p)} style={{ accentColor: 'var(--green)' }} />
          Held only
        </label>
      </div>

      {/* ── Main Table ───────────────────────────────── */}
      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading mutual fund data...</div>
      ) : filtered.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>No mutual funds found.</div>
      ) : (
        <div style={{ overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.02)' }}>
                {isCol('name') && <th style={thStyle} onClick={() => handleSort('name')}>Fund{arrow('name')}</th>}
                {isCol('units') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('units')}>Units{arrow('units')}</th>}
                {isCol('avgNav') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('avgNav')}>Avg NAV{arrow('avgNav')}</th>}
                {isCol('invested') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('invested')}>Invested{arrow('invested')}</th>}
                {isCol('currentNav') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('currentNav')}>Current NAV{arrow('currentNav')}</th>}
                {isCol('currentValue') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('currentValue')}>Current Value{arrow('currentValue')}</th>}
                {isCol('unrealizedPL') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('unrealizedPL')}>Unrealized P&L{arrow('unrealizedPL')}</th>}
                {isCol('realizedPL') && <th style={{ ...thStyle, textAlign: 'right' }} onClick={() => handleSort('realizedPL')}>Realized P&L{arrow('realizedPL')}</th>}
                {isCol('52w') && <th style={thStyle}>52W Range</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map(f => {
                const isExpanded = expandedFund === f.fund_code;
                const plColor = f.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)';
                const rplColor = f.realized_pl >= 0 ? 'var(--green)' : 'var(--red)';
                const visColCount = COL_DEFS.filter(c => isCol(c.id)).length;

                return (
                  <React.Fragment key={f.fund_code}>
                    {/* ── Summary row ─────────────────────── */}
                    <tr
                      onClick={() => setExpandedFund(isExpanded ? null : f.fund_code)}
                      style={{ cursor: 'pointer', background: isExpanded ? 'rgba(99,102,241,0.06)' : 'transparent', transition: 'background 0.15s' }}
                      onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-hover)'; }}
                      onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}
                    >
                      {isCol('name') && (() => {
                        const sipCfg = getSIPForFund(f.fund_code);
                        return (
                        <td style={tdStyle}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <div style={{ flex: 1 }}>
                              <span style={{ fontWeight: 600, color: 'var(--text)', fontSize: '13px' }}>
                                {isExpanded ? '▾' : '▸'}{' '}
                                {f.name.replace(/\s*-\s*Direct\s*(Plan\s*)?(Growth|Dividend)?\.?$/i, '').replace(/\s*Direct\s*(Growth|Dividend)?\.?$/i, '')}
                              </span>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 1 }}>
                                {f.num_held_lots} lot{f.num_held_lots !== 1 ? 's' : ''}
                                {f.num_sold_lots > 0 && <span> • {f.num_sold_lots} redeemed</span>}
                                {sipCfg && sipCfg.enabled && (
                                  <span style={{ marginLeft: 6, padding: '1px 5px', borderRadius: 3, background: 'rgba(0,210,106,0.12)', color: 'var(--green)', fontSize: '10px', fontWeight: 600 }}>
                                    SIP ₹{Number(sipCfg.amount).toLocaleString('en-IN')}/{sipCfg.frequency === 'weekly' ? 'wk' : sipCfg.frequency === 'quarterly' ? 'qtr' : 'mo'}
                                  </span>
                                )}
                              </div>
                            </div>
                            {f.total_held_units > 0 && onRedeemMF && (
                              <button
                                onClick={(e) => { e.stopPropagation(); onRedeemMF(f); }}
                                style={{ padding: '2px 8px', fontSize: '11px', fontWeight: 500, background: 'rgba(255,71,87,0.1)', color: 'var(--red)', border: '1px solid rgba(255,71,87,0.2)', borderRadius: 4, cursor: 'pointer', whiteSpace: 'nowrap' }}
                              >
                                Redeem
                              </button>
                            )}
                          </div>
                        </td>
                        );
                      })()}
                      {isCol('units') && <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'monospace', fontSize: '12px' }}>{formatUnits(f.total_held_units)}</td>}
                      {isCol('avgNav') && <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(f.avg_nav)}</td>}
                      {isCol('invested') && <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 500 }}>{formatINR(f.total_invested)}</td>}
                      {isCol('currentNav') && (
                        <td style={{ ...tdStyle, textAlign: 'right' }}>
                          <span style={{ color: f.is_above_avg_nav ? 'var(--green)' : 'var(--red)' }}>{formatINR(f.current_nav)}</span>
                        </td>
                      )}
                      {isCol('currentValue') && <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600 }}>{formatINR(f.current_value)}</td>}
                      {isCol('unrealizedPL') && (
                        <td style={{ ...tdStyle, textAlign: 'right' }}>
                          <div style={{ color: plColor, fontWeight: 600 }}>
                            {f.unrealized_pl >= 0 ? '+' : ''}{formatINR(f.unrealized_pl)}
                          </div>
                          <div style={{ fontSize: '11px', color: plColor, opacity: 0.8 }}>
                            {f.unrealized_pl_pct >= 0 ? '+' : ''}{f.unrealized_pl_pct?.toFixed(2)}%
                          </div>
                        </td>
                      )}
                      {isCol('realizedPL') && (
                        <td style={{ ...tdStyle, textAlign: 'right', color: rplColor, fontWeight: 500 }}>
                          {f.realized_pl >= 0 ? '+' : ''}{formatINR(f.realized_pl)}
                        </td>
                      )}
                      {isCol('52w') && (
                        <td style={tdStyle}>
                          <NavRangeBar low={f.week_52_low} high={f.week_52_high} current={f.current_nav} avg={f.avg_nav} />
                        </td>
                      )}
                    </tr>

                    {/* ── Expanded detail ─────────────────── */}
                    {isExpanded && (
                      <tr>
                        <td colSpan={visColCount} style={{ padding: '12px 16px 16px', background: 'rgba(99,102,241,0.03)', borderBottom: '2px solid var(--border)' }}>
                          {/* ── Action buttons ──────────── */}
                          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
                            {onBuyMF && (
                              <button
                                onClick={() => onBuyMF({ fund_code: f.fund_code, name: f.name, fund_name: f.name })}
                                className="btn btn-primary"
                                style={{ padding: '4px 12px', fontSize: '12px' }}
                              >
                                + Buy {f.name.replace(/\s*-\s*Direct\s*(Plan\s*)?(Growth|Dividend)?\.?$/i, '').replace(/\s*Direct\s*(Growth|Dividend)?\.?$/i, '').substring(0, 25)}
                              </button>
                            )}
                            {onConfigSIP && (
                              <button
                                onClick={() => onConfigSIP(f)}
                                style={{
                                  padding: '4px 12px', fontSize: '12px', fontWeight: 500,
                                  background: getSIPForFund(f.fund_code) ? 'rgba(0,210,106,0.1)' : 'var(--bg-hover)',
                                  color: getSIPForFund(f.fund_code) ? 'var(--green)' : 'var(--text-dim)',
                                  border: `1px solid ${getSIPForFund(f.fund_code) ? 'rgba(0,210,106,0.3)' : 'var(--border)'}`,
                                  borderRadius: 6, cursor: 'pointer',
                                }}
                              >
                                {getSIPForFund(f.fund_code) ? '⚙ Edit SIP' : '⚙ Setup SIP'}
                              </button>
                            )}
                          </div>
                          <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap' }}>
                            {/* ── Held Lots ─────────────── */}
                            {f.held_lots && f.held_lots.length > 0 && (
                              <div style={{ flex: '1 1 400px' }}>
                                <h4 style={{ margin: '0 0 8px', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                                  Held Lots ({f.held_lots.length})
                                  <span style={{ fontWeight: 400, fontSize: '12px', color: 'var(--text-muted)', marginLeft: 8 }}>
                                    {formatUnits(f.total_held_units)} units
                                  </span>
                                </h4>
                                <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'auto', width: 'fit-content', maxWidth: '100%' }}>
                                  <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
                                    <thead>
                                      <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                                        <th style={subTh}>Buy Date</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Units</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>NAV</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Cost</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Current</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>P&L</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {f.held_lots.map((lot, i) => {
                                        const lotPlColor = lot.pl >= 0 ? 'var(--green)' : 'var(--red)';
                                        return (
                                          <tr key={lot.id || i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                            <td style={{ ...subTd, borderLeft: `3px solid ${lot.is_ltcg ? 'var(--green)' : '#f59e0b'}` }}>
                                              <span style={{ fontSize: '12px' }}>{formatDate(lot.buy_date)}</span>
                                              <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: 4 }}>
                                                {durationText(lot.buy_date)}
                                              </span>
                                              <span style={{ fontSize: '9px', marginLeft: 4, padding: '1px 4px', borderRadius: 3, background: lot.is_ltcg ? 'rgba(0,210,106,0.15)' : 'rgba(245,158,11,0.15)', color: lot.is_ltcg ? 'var(--green)' : '#f59e0b' }}>
                                                {lot.is_ltcg ? 'LT' : 'ST'}
                                              </span>
                                            </td>
                                            <td style={{ ...subTd, textAlign: 'right', fontFamily: 'monospace', fontSize: '11px' }}>{formatUnits(lot.units)}</td>
                                            <td style={{ ...subTd, textAlign: 'right' }}>{formatINR(lot.buy_price)}</td>
                                            <td style={{ ...subTd, textAlign: 'right' }}>{formatINR(lot.buy_cost)}</td>
                                            <td style={{ ...subTd, textAlign: 'right' }}>{formatINR(lot.current_value)}</td>
                                            <td style={{ ...subTd, textAlign: 'right', color: lotPlColor, fontWeight: 500 }}>
                                              {lot.pl >= 0 ? '+' : ''}{formatINR(lot.pl)}
                                              <div style={{ fontSize: '10px', opacity: 0.8 }}>
                                                {lot.pl_pct >= 0 ? '+' : ''}{lot.pl_pct?.toFixed(1)}%
                                              </div>
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}

                            {/* ── Redeemed (Sold) Lots ──── */}
                            {f.sold_lots && f.sold_lots.length > 0 && (
                              <div style={{ flex: '1 1 400px' }}>
                                <h4 style={{ margin: '0 0 8px', fontSize: '13px', fontWeight: 600, color: 'var(--text)' }}>
                                  Redemptions ({f.sold_lots.length})
                                  <span style={{ fontWeight: 400, fontSize: '12px', color: 'var(--text-muted)', marginLeft: 8 }}>
                                    {formatUnits(f.total_sold_units)} units
                                    {' • Net P&L: '}
                                    <span style={{ color: f.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                                      {f.realized_pl >= 0 ? '+' : ''}{formatINR(f.realized_pl)}
                                    </span>
                                  </span>
                                </h4>
                                <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'auto', width: 'fit-content', maxWidth: '100%' }}>
                                  <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
                                    <thead>
                                      <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                                        <th style={subTh}>Buy Date</th>
                                        <th style={subTh}>Sell Date</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Units</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Buy NAV</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>Sell NAV</th>
                                        <th style={{ ...subTh, textAlign: 'right' }}>P&L</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {f.sold_lots.map((s, i) => {
                                        const sPlColor = s.realized_pl >= 0 ? 'var(--green)' : 'var(--red)';
                                        return (
                                          <tr key={s.id || i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                                            <td style={subTd}>{formatDate(s.buy_date)}</td>
                                            <td style={subTd}>{formatDate(s.sell_date)}</td>
                                            <td style={{ ...subTd, textAlign: 'right', fontFamily: 'monospace', fontSize: '11px' }}>{formatUnits(s.units)}</td>
                                            <td style={{ ...subTd, textAlign: 'right' }}>{formatINR(s.buy_nav)}</td>
                                            <td style={{ ...subTd, textAlign: 'right' }}>{formatINR(s.sell_nav)}</td>
                                            <td style={{ ...subTd, textAlign: 'right', color: sPlColor, fontWeight: 500 }}>
                                              {s.realized_pl >= 0 ? '+' : ''}{formatINR(s.realized_pl)}
                                            </td>
                                          </tr>
                                        );
                                      })}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}
                          </div>

                          {/* LTCG/STCG summary */}
                          <div style={{ display: 'flex', gap: '16px', marginTop: '12px', flexWrap: 'wrap' }}>
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
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}

              {/* ── Totals row ─────────────────────────── */}
              <tr style={{ background: 'rgba(255,255,255,0.04)', fontWeight: 600 }}>
                {isCol('name') && <td style={{ ...tdStyle, fontSize: '12px' }}>TOTAL ({filtered.length} funds)</td>}
                {isCol('units') && <td style={tdStyle} />}
                {isCol('avgNav') && <td style={tdStyle} />}
                {isCol('invested') && <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(totalInvested)}</td>}
                {isCol('currentNav') && <td style={tdStyle} />}
                {isCol('currentValue') && <td style={{ ...tdStyle, textAlign: 'right' }}>{formatINR(totalValue)}</td>}
                {isCol('unrealizedPL') && (
                  <td style={{ ...tdStyle, textAlign: 'right', color: totalUPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {totalUPL >= 0 ? '+' : ''}{formatINR(totalUPL)}
                    <div style={{ fontSize: '11px', opacity: 0.8 }}>
                      {totalInvested > 0 ? `${((totalUPL / totalInvested) * 100).toFixed(2)}%` : ''}
                    </div>
                  </td>
                )}
                {isCol('realizedPL') && (
                  <td style={{ ...tdStyle, textAlign: 'right', color: totalRPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                    {totalRPL >= 0 ? '+' : ''}{formatINR(totalRPL)}
                  </td>
                )}
                {isCol('52w') && <td style={tdStyle} />}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
