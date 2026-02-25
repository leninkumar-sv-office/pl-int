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
  return `${String(d.getDate()).padStart(2, '0')}-${MONTHS[d.getMonth()]}-${d.getFullYear()}`;
};

const statusColor = (s) => {
  switch (s) {
    case 'Active': return { bg: 'var(--green-bg)', color: 'var(--green)' };
    case 'Closed': return { bg: 'var(--red-bg, rgba(239,68,68,0.1))', color: 'var(--red)' };
    case 'Frozen': return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
    default: return { bg: 'var(--blue-bg)', color: 'var(--blue)' };
  }
};

const gainColor = (val) => val > 0 ? 'var(--green)' : val < 0 ? 'var(--red)' : 'var(--text-dim)';

/* ── Main table column definitions ─────────────────────── */
const COL_DEFS = [
  { id: 'pran',             label: 'PRAN' },
  { id: 'tier',             label: 'Tier' },
  { id: 'fundManager',      label: 'Fund Manager' },
  { id: 'scheme',           label: 'Scheme' },
  { id: 'startDate',        label: 'Start Date' },
  { id: 'yearsActive',      label: 'Years' },
  { id: 'totalContributed', label: 'Total Contributed' },
  { id: 'currentValue',     label: 'Current Value' },
  { id: 'gain',             label: 'Gain/Loss' },
  { id: 'status',           label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'npsVisibleCols_v1';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(ALL_COL_IDS);
}

/* ── Sub-table styles ─────────────────────────────────── */
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

/* ── NPS Detail Row ──────────────────────────────── */
function NPSDetail({ nps, onEdit, onDelete, onAddContribution }) {
  const sc = statusColor(nps.status);
  const contributions = nps.contributions || [];

  return (
    <div style={{ background: 'var(--bg)', borderTop: '1px solid var(--border)', padding: '20px 24px' }}>
      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>Actions:</span>
        {onAddContribution && nps.status === 'Active' && (
          <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); onAddContribution(nps); }}>+ Add Contribution</button>
        )}
        {onEdit && (
          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(nps); }}>Edit</button>
        )}
        {onDelete && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete NPS account "${nps.account_name}"?`)) onDelete(nps.id); }}>
            Delete
          </button>
        )}
      </div>

      {/* Stats bar */}
      <div style={{
        display: 'flex', gap: '32px', marginBottom: '20px', padding: '14px 16px', background: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Account Name</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{nps.account_name}</div>
        </div>
        {nps.pran && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>PRAN</div>
            <div style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'monospace' }}>{nps.pran}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Tier</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{nps.tier}</div>
        </div>
        {nps.fund_manager && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Fund Manager</div>
            <div style={{ fontSize: '15px', fontWeight: 600 }}>{nps.fund_manager}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Scheme</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{nps.scheme_preference}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Start Date</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(nps.start_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Years Active</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{nps.years_active || 0}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Contributed</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(nps.total_contributed)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Value</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(nps.current_value)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Gain/Loss</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: gainColor(nps.gain) }}>
            {formatINR(nps.gain)} ({nps.gain_pct >= 0 ? '+' : ''}{nps.gain_pct}%)
          </div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: sc.bg, color: sc.color }}>{nps.status}</span>
        </div>
        {nps.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{nps.remarks}</div>
          </div>
        )}
      </div>

      {/* Contributions list */}
      {contributions.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)' }}>
            Contributions ({contributions.length})
          </div>
          <div style={{
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <th style={heldTh}>#</th>
                  <th style={heldTh}>Date</th>
                  <th style={{ ...heldTh, textAlign: 'right' }}>Amount</th>
                  <th style={heldTh}>Remarks</th>
                </tr>
              </thead>
              <tbody>
                {contributions.slice().sort((a, b) => (b.date || '').localeCompare(a.date || '')).map((c, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ ...heldTd, color: 'var(--text-muted)' }}>{contributions.length - i}</td>
                    <td style={heldTd}>{formatDate(c.date)}</td>
                    <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600 }}>{formatINR(c.amount)}</td>
                    <td style={{ ...heldTd, color: 'var(--text-dim)' }}>{c.remarks || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Table ───────────────────────────────────── */
export default function NPSTable({ accounts, loading, npsDashboard, onAddNPS, onEditNPS, onDeleteNPS, onAddContribution }) {
  const [expandedId, setExpandedId] = useState(null);
  const [sortKey, setSortKey] = useState('account_name');
  const [sortDir, setSortDir] = useState('asc');
  const [visibleCols, setVisibleCols] = useState(loadVisibleCols);
  const [colPickerOpen, setColPickerOpen] = useState(false);
  const colPickerRef = useRef(null);
  const [searchTerm, setSearchTerm] = useState('');
  const searchRef = useRef(null);

  const col = (id) => visibleCols.has(id);

  const toggleCol = (id) => {
    setVisibleCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      try { localStorage.setItem(LS_KEY, JSON.stringify([...next])); } catch (_) {}
      return next;
    });
  };
  const showAllCols = () => { const all = new Set(ALL_COL_IDS); setVisibleCols(all); try { localStorage.setItem(LS_KEY, JSON.stringify([...all])); } catch (_) {} };
  const hideAllCols = () => { setVisibleCols(new Set()); try { localStorage.setItem(LS_KEY, JSON.stringify([])); } catch (_) {} };

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
    if (sortKey !== field) return <span style={{ opacity: 0.3, fontSize: '10px' }}> &#x21C5;</span>;
    return <span style={{ fontSize: '10px' }}> {sortDir === 'asc' ? '\u2191' : '\u2193'}</span>;
  };

  const q = searchTerm.trim().toLowerCase();
  let filtered = (accounts || []).filter(nps => {
    if (q) return nps.account_name.toLowerCase().includes(q) || (nps.pran || '').toLowerCase().includes(q) || (nps.fund_manager || '').toLowerCase().includes(q);
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'account_name':     va = a.account_name; vb = b.account_name; break;
      case 'pran':             va = a.pran || ''; vb = b.pran || ''; break;
      case 'tier':             va = a.tier; vb = b.tier; break;
      case 'fundManager':      va = a.fund_manager || ''; vb = b.fund_manager || ''; break;
      case 'scheme':           va = a.scheme_preference || ''; vb = b.scheme_preference || ''; break;
      case 'startDate':        va = a.start_date; vb = b.start_date; break;
      case 'yearsActive':      va = a.years_active || 0; vb = b.years_active || 0; break;
      case 'totalContributed': va = a.total_contributed || 0; vb = b.total_contributed || 0; break;
      case 'currentValue':     va = a.current_value || 0; vb = b.current_value || 0; break;
      case 'gain':             va = a.gain || 0; vb = b.gain || 0; break;
      case 'status':           va = a.status; vb = b.status; break;
      default:                 va = a.account_name; vb = b.account_name;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  const activeCount = (accounts || []).filter(a => a.status === 'Active').length;
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  if (loading && (accounts || []).length === 0) {
    return <div className="loading"><div className="spinner" />Loading NPS accounts...</div>;
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">National Pension System (NPS)</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">{activeCount} active</span>
          <span className="section-badge" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            {(accounts || []).length} total
          </span>
        </div>
      </div>

      {/* Summary Bar */}
      {npsDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Contributed</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(npsDashboard.total_contributed)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Value</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(npsDashboard.current_value)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Gain/Loss</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: gainColor(npsDashboard.total_gain) }}>
              {formatINR(npsDashboard.total_gain)} ({npsDashboard.gain_pct >= 0 ? '+' : ''}{npsDashboard.gain_pct}%)
            </div>
          </div>
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{npsDashboard.active_count}</div>
          </div>
        </div>
      )}

      {/* Search + Column Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef} type="text" placeholder="Search by account name, PRAN, or fund manager..."
            value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)}
            style={{ width: '100%', padding: '8px 30px 8px 34px', background: 'var(--bg-input)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text)', fontSize: '13px', outline: 'none' }}
          />
          <span style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: '14px', pointerEvents: 'none' }}>&#x1F50D;</span>
          {searchTerm && (
            <span onClick={() => { setSearchTerm(''); if (searchRef.current) searchRef.current.focus(); }}
              style={{ position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)', fontSize: '16px', cursor: 'pointer', lineHeight: 1 }}>&#x2715;</span>
          )}
        </div>
        {q && <span style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>}
        <div style={{ position: 'relative' }} ref={colPickerRef}>
          <button className="btn btn-ghost btn-sm" onClick={() => setColPickerOpen(p => !p)} title="Toggle columns"
            style={{ fontSize: '16px', padding: '4px 8px', lineHeight: 1 }}>&#x2699;</button>
          {colPickerOpen && (
            <div style={{ position: 'absolute', right: 0, top: '110%', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '8px 0', zIndex: 100, minWidth: '200px', boxShadow: 'var(--shadow)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 12px 8px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer' }} onClick={showAllCols}>Show All</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer' }} onClick={hideAllCols}>Hide All</span>
              </div>
              {COL_DEFS.map(c => (
                <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', cursor: 'pointer', fontSize: '13px', color: 'var(--text)' }}>
                  <input type="checkbox" checked={visibleCols.has(c.id)} onChange={() => toggleCol(c.id)} />
                  {c.label}
                </label>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="table-container">
        <table style={{ width: '100%', borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid var(--border)' }}>
              <th style={{ width: '30px', padding: '10px 8px' }}></th>
              <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }}
                onClick={() => handleSort('account_name')}>Account<SortIcon field="account_name" /></th>
              {col('pran') && <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('pran')}>PRAN<SortIcon field="pran" /></th>}
              {col('tier') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('tier')}>Tier<SortIcon field="tier" /></th>}
              {col('fundManager') && <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('fundManager')}>Fund Manager<SortIcon field="fundManager" /></th>}
              {col('scheme') && <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('scheme')}>Scheme<SortIcon field="scheme" /></th>}
              {col('startDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('yearsActive') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('yearsActive')}>Years<SortIcon field="yearsActive" /></th>}
              {col('totalContributed') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('totalContributed')}>Contributed<SortIcon field="totalContributed" /></th>}
              {col('currentValue') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('currentValue')}>Value<SortIcon field="currentValue" /></th>}
              {col('gain') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('gain')}>Gain/Loss<SortIcon field="gain" /></th>}
              {col('status') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('status')}>Status<SortIcon field="status" /></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={TOTAL_COLS} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {q ? 'No matching NPS accounts found' : 'No NPS accounts yet. Click "+ Add NPS" to add one.'}
              </td></tr>
            )}
            {filtered.map(nps => {
              const isExpanded = expandedId === nps.id;
              const sc = statusColor(nps.status);
              return (
                <React.Fragment key={nps.id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : nps.id)}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', background: isExpanded ? 'var(--bg-card-hover)' : 'transparent', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}>
                    <td style={{ padding: '10px 8px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--text)' }}>
                      {nps.account_name}
                    </td>
                    {col('pran') && <td style={{ padding: '10px 12px', fontFamily: 'monospace', color: 'var(--text-dim)' }}>{nps.pran || '-'}</td>}
                    {col('tier') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>{nps.tier}</td>}
                    {col('fundManager') && <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>{nps.fund_manager || '-'}</td>}
                    {col('scheme') && <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>{nps.scheme_preference || '-'}</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(nps.start_date)}</td>}
                    {col('yearsActive') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{nps.years_active || 0}</td>}
                    {col('totalContributed') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(nps.total_contributed)}</td>}
                    {col('currentValue') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(nps.current_value)}</td>}
                    {col('gain') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: gainColor(nps.gain) }}>
                      {formatINR(nps.gain)} <span style={{ fontSize: '11px' }}>({nps.gain_pct >= 0 ? '+' : ''}{nps.gain_pct}%)</span>
                    </td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{nps.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <NPSDetail nps={nps} onEdit={onEditNPS} onDelete={onDeleteNPS} onAddContribution={onAddContribution} />
                    </td></tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
