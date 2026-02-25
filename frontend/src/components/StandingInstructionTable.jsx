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
    case 'Expired': return { bg: 'var(--red-bg)', color: 'var(--red)' };
    case 'Cancelled': return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
    default: return { bg: 'var(--blue-bg)', color: 'var(--blue)' };
  }
};

const purposeColor = (p) => {
  switch (p) {
    case 'SIP': return { bg: 'var(--green-bg)', color: 'var(--green)' };
    case 'EMI': return { bg: 'var(--blue-bg)', color: 'var(--blue)' };
    case 'Utility': return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
    case 'Insurance': return { bg: 'rgba(168,85,247,0.1)', color: 'var(--purple)' };
    default: return { bg: 'rgba(255,255,255,0.06)', color: 'var(--text-dim)' };
  }
};

/* ── Column Definitions ─────────────────────────────── */
const COL_DEFS = [
  { id: 'beneficiary', label: 'Beneficiary' },
  { id: 'amount',      label: 'Amount' },
  { id: 'frequency',   label: 'Frequency' },
  { id: 'purpose',     label: 'Purpose' },
  { id: 'mandateType', label: 'Mandate' },
  { id: 'startDate',   label: 'Start' },
  { id: 'expiry',      label: 'Expiry' },
  { id: 'daysLeft',    label: 'Days Left' },
  { id: 'alert',       label: 'Alert' },
  { id: 'status',      label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'siVisibleCols_v1';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(ALL_COL_IDS);
}

/* ── SI Detail Row ───────────────────────────────── */
function SIDetail({ si, onEdit, onDelete }) {
  const sc = statusColor(si.status);
  const pc = purposeColor(si.purpose);

  return (
    <div style={{ background: 'var(--bg)', borderTop: '1px solid var(--border)', padding: '20px 24px' }}>
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>Actions:</span>
        {onEdit && (
          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(si); }}>Edit</button>
        )}
        {onDelete && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete SI "${si.beneficiary}" at ${si.bank}?`)) onDelete(si.id); }}>
            Delete
          </button>
        )}
      </div>

      <div style={{
        display: 'flex', gap: '32px', padding: '14px 16px', background: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bank</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{si.bank}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Beneficiary</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{si.beneficiary}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Amount ({si.frequency})</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(si.amount)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Purpose</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: pc.bg, color: pc.color }}>{si.purpose}</span>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Mandate Type</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{si.mandate_type}</div>
        </div>
        {si.account_number && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Account</div>
            <div style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'monospace' }}>{si.account_number}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Start</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(si.start_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Expiry</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(si.expiry_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Alert Before</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{si.alert_days} days</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: sc.bg, color: sc.color }}>{si.status}</span>
        </div>
        {si.days_to_expiry !== undefined && si.status === 'Active' && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Days Left</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: si.days_to_expiry <= 7 ? 'var(--red)' : si.days_to_expiry <= si.alert_days ? 'var(--yellow)' : 'var(--text)' }}>
              {si.days_to_expiry > 0 ? `${si.days_to_expiry}d` : 'Expired'}
            </div>
          </div>
        )}
        {si.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{si.remarks}</div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Main Table ───────────────────────────────────── */
export default function StandingInstructionTable({ instructions, loading, siDashboard, onAddSI, onEditSI, onDeleteSI }) {
  const [expandedId, setExpandedId] = useState(null);
  const [sortKey, setSortKey] = useState('bank');
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
  let filtered = (instructions || []).filter(s => {
    if (q) return s.bank.toLowerCase().includes(q) || s.beneficiary.toLowerCase().includes(q) || s.purpose.toLowerCase().includes(q) || s.mandate_type.toLowerCase().includes(q);
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'bank':        va = a.bank; vb = b.bank; break;
      case 'beneficiary': va = a.beneficiary; vb = b.beneficiary; break;
      case 'amount':      va = a.amount; vb = b.amount; break;
      case 'frequency':   va = a.frequency; vb = b.frequency; break;
      case 'purpose':     va = a.purpose; vb = b.purpose; break;
      case 'mandateType': va = a.mandate_type; vb = b.mandate_type; break;
      case 'startDate':   va = a.start_date; vb = b.start_date; break;
      case 'expiry':      va = a.expiry_date; vb = b.expiry_date; break;
      case 'daysLeft':    va = a.days_to_expiry; vb = b.days_to_expiry; break;
      case 'alert':       va = a.alert_days; vb = b.alert_days; break;
      case 'status':      va = a.status; vb = b.status; break;
      default:            va = a.bank; vb = b.bank;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  const activeCount = (instructions || []).filter(s => s.status === 'Active').length;
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  const thStyle = { padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' };
  const thRight = { ...thStyle, textAlign: 'right' };
  const thCenter = { ...thStyle, textAlign: 'center' };

  if (loading && (instructions || []).length === 0) {
    return <div className="loading"><div className="spinner" />Loading standing instructions...</div>;
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Standing Instructions</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">{activeCount} active</span>
          <span className="section-badge" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            {(instructions || []).length} total
          </span>
        </div>
      </div>

      {/* Summary Bar */}
      {siDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Monthly Outflow</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(siDashboard.total_monthly_outflow)}</div>
          </div>
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active Mandates</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{siDashboard.active_count}</div>
          </div>
          {siDashboard.expiring_soon > 0 && (
            <div style={{ flex: '1 1 80px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Expiring Soon</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--yellow)' }}>{siDashboard.expiring_soon}</div>
            </div>
          )}
        </div>
      )}

      {/* Search + Column Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef} type="text" placeholder="Search by bank, beneficiary, purpose..."
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
            <div style={{ position: 'absolute', right: 0, top: '110%', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '8px 0', zIndex: 100, minWidth: '180px', boxShadow: 'var(--shadow)' }}>
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
              <th style={thStyle} onClick={() => handleSort('bank')}>Bank<SortIcon field="bank" /></th>
              {col('beneficiary') && <th style={thStyle} onClick={() => handleSort('beneficiary')}>Beneficiary<SortIcon field="beneficiary" /></th>}
              {col('amount') && <th style={thRight} onClick={() => handleSort('amount')}>Amount<SortIcon field="amount" /></th>}
              {col('frequency') && <th style={thCenter} onClick={() => handleSort('frequency')}>Frequency<SortIcon field="frequency" /></th>}
              {col('purpose') && <th style={thCenter} onClick={() => handleSort('purpose')}>Purpose<SortIcon field="purpose" /></th>}
              {col('mandateType') && <th style={thCenter} onClick={() => handleSort('mandateType')}>Mandate<SortIcon field="mandateType" /></th>}
              {col('startDate') && <th style={thRight} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('expiry') && <th style={thRight} onClick={() => handleSort('expiry')}>Expiry<SortIcon field="expiry" /></th>}
              {col('daysLeft') && <th style={thRight} onClick={() => handleSort('daysLeft')}>Days Left<SortIcon field="daysLeft" /></th>}
              {col('alert') && <th style={thRight} onClick={() => handleSort('alert')}>Alert<SortIcon field="alert" /></th>}
              {col('status') && <th style={thCenter} onClick={() => handleSort('status')}>Status<SortIcon field="status" /></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={TOTAL_COLS} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {q ? 'No matching instructions found' : 'No standing instructions yet. Click "+ Add SI" to add one.'}
              </td></tr>
            )}
            {filtered.map(s => {
              const isExpanded = expandedId === s.id;
              const sc = statusColor(s.status);
              const pc = purposeColor(s.purpose);
              const daysColor = s.days_to_expiry <= 7 ? 'var(--red)' : s.days_to_expiry <= s.alert_days ? 'var(--yellow)' : 'var(--text)';
              return (
                <React.Fragment key={s.id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : s.id)}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', background: isExpanded ? 'var(--bg-card-hover)' : 'transparent', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}>
                    <td style={{ padding: '10px 8px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--text)' }}>
                      {s.bank}
                      {s.days_to_expiry > 0 && s.days_to_expiry <= s.alert_days && s.status === 'Active' && (
                        <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--yellow)', fontWeight: 400 }}>({s.days_to_expiry}d left)</span>
                      )}
                    </td>
                    {col('beneficiary') && <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>{s.beneficiary}</td>}
                    {col('amount') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(s.amount)}</td>}
                    {col('frequency') && <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--text-dim)' }}>{s.frequency}</td>}
                    {col('purpose') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: pc.bg, color: pc.color }}>{s.purpose}</span>
                    </td>}
                    {col('mandateType') && <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--text-dim)' }}>{s.mandate_type}</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(s.start_date)}</td>}
                    {col('expiry') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(s.expiry_date)}</td>}
                    {col('daysLeft') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: daysColor }}>
                      {s.days_to_expiry > 0 ? `${s.days_to_expiry}d` : s.status === 'Active' ? 'Expired' : '-'}
                    </td>}
                    {col('alert') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{s.alert_days}d</td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{s.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <SIDetail si={s} onEdit={onEditSI} onDelete={onDeleteSI} />
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
