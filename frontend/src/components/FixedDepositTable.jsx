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
    case 'Matured': return { bg: 'var(--blue-bg)', color: 'var(--blue)' };
    case 'Premature': case 'Closed': return { bg: 'var(--red-bg)', color: 'var(--red)' };
    default: return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
  }
};

const typeColor = (t) => {
  switch (t) {
    case 'FD': return { bg: 'var(--blue-bg)', color: 'var(--blue)' };
    case 'MIS': return { bg: 'rgba(168,85,247,0.1)', color: 'var(--purple, #a855f7)' };
    default: return { bg: 'rgba(255,255,255,0.06)', color: 'var(--text-dim)' };
  }
};

/* ── Main table column definitions ─────────────────────── */
const COL_DEFS = [
  { id: 'type',          label: 'Type' },
  { id: 'principal',     label: 'Principal' },
  { id: 'rate',          label: 'Rate %' },
  { id: 'payout',        label: 'Payout' },
  { id: 'tenure',        label: 'Tenure' },
  { id: 'startDate',     label: 'Start Date' },
  { id: 'maturityDate',  label: 'Maturity Date' },
  { id: 'maturityAmt',   label: 'Maturity Amt' },
  { id: 'interest',      label: 'Interest Earned' },
  { id: 'interestProj',  label: 'Interest Projected' },
  { id: 'installments',  label: 'Installments' },
  { id: 'tds',           label: 'TDS' },
  { id: 'status',        label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'fdVisibleCols_v2';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  const DEFAULT_HIDDEN = ['tds', 'interestProj'];
  return new Set(ALL_COL_IDS.filter(id => !DEFAULT_HIDDEN.includes(id)));
}

/* ── Installment sub-table column definitions ──────────── */
const INST_COL_DEFS = [
  { id: 'month',    label: '#' },
  { id: 'date',     label: 'Date' },
  { id: 'invested', label: 'Amount Invested' },
  { id: 'earned',   label: 'Interest Earned' },
  { id: 'projected',label: 'Interest Projected' },
];
const INST_COL_LS_KEY = 'fdInstHiddenCols';

function loadInstHiddenCols() {
  try {
    const saved = localStorage.getItem(INST_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set();
}

/* ── Installment sub-table styles ─────────────────────── */
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

/* ── FD Detail Row ───────────────────────────────── */
function FDDetail({ fd, onEdit, onDelete }) {
  const sc = statusColor(fd.status);
  const tc = typeColor(fd.type);
  const installments = fd.installments || [];

  // Installment column visibility
  const [hiddenInstCols, setHiddenInstCols] = useState(loadInstHiddenCols);
  const [showColPicker, setShowColPicker] = useState(false);
  const colPickerRef = useRef(null);
  const iCol = (id) => !hiddenInstCols.has(id);

  const toggleInstCol = (id) => {
    setHiddenInstCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      try { localStorage.setItem(INST_COL_LS_KEY, JSON.stringify([...next])); } catch (_) {}
      return next;
    });
  };

  useEffect(() => {
    if (!showColPicker) return;
    const handler = (e) => { if (colPickerRef.current && !colPickerRef.current.contains(e.target)) setShowColPicker(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showColPicker]);

  const pastInstallments = installments.filter(i => i.is_past);
  const futureInstallments = installments.filter(i => !i.is_past);
  const totalIntEarned = installments.reduce((s, i) => s + (i.interest_earned || 0), 0);
  const totalIntProjected = installments.reduce((s, i) => s + (i.interest_projected || 0), 0);
  const totalInvested = installments.reduce((s, i) => s + (i.amount_invested || 0), 0);

  return (
    <div style={{ background: 'var(--bg)', borderTop: '1px solid var(--border)', padding: '20px 24px' }}>
      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>Actions:</span>
        {onEdit && fd.source === 'manual' && (
          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(fd); }}>Edit</button>
        )}
        {onDelete && fd.source === 'manual' && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete FD "${fd.name}"?`)) onDelete(fd.id); }}>
            Delete
          </button>
        )}
        {fd.source === 'xlsx' && (
          <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
            Imported from Excel — edit the source file to modify
          </span>
        )}
      </div>

      {/* Stats bar */}
      <div style={{
        display: 'flex', gap: '32px', marginBottom: '20px', padding: '14px 16px', background: 'var(--bg-card)',
        borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', flexWrap: 'wrap',
      }}>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Name</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{fd.name}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bank</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{fd.bank}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Type</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: tc.bg, color: tc.color }}>{fd.type || 'FD'}</span>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Principal / Invested</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(fd.total_invested || fd.principal)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Rate</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{fd.interest_rate}%</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Payout</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{fd.interest_payout || 'Maturity'}</div>
        </div>
        {fd.sip_amount > 0 && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>SIP Amount</div>
            <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(fd.sip_amount)}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Start</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(fd.start_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(fd.maturity_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity Amt</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(fd.maturity_amount)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Earned</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(fd.interest_earned)}</div>
        </div>
        {fd.interest_projected > 0 && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Projected</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(fd.interest_projected)}</div>
          </div>
        )}
        {fd.tds > 0 && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>TDS</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--red)' }}>{formatINR(fd.tds)}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: sc.bg, color: sc.color }}>{fd.status}</span>
        </div>
        {fd.days_to_maturity > 0 && fd.status === 'Active' && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Days Left</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: fd.days_to_maturity <= 90 ? 'var(--yellow)' : 'var(--text)' }}>{fd.days_to_maturity}d</div>
          </div>
        )}
        {fd.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{fd.remarks}</div>
          </div>
        )}
      </div>

      {/* Installment Schedule sub-table */}
      {installments.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span>Installment Schedule ({installments.length})</span>
            <span style={{ display: 'flex', gap: '8px', fontSize: '10px', fontWeight: 500 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#22c55e', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Past ({pastInstallments.length})</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#3b82f6', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Future ({futureInstallments.length})</span>
              </span>
            </span>
            {/* Sub-table column picker */}
            <div style={{ position: 'relative' }} ref={colPickerRef}>
              <button
                onClick={(e) => { e.stopPropagation(); setShowColPicker(v => !v); }}
                style={{
                  background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
                  padding: '3px 8px', fontSize: '11px', color: 'var(--text-dim)', cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: '4px',
                }}
                title="Show/hide columns"
              >
                <span style={{ fontSize: '13px' }}>&#9776;</span> Columns
              </button>
              {showColPicker && (
                <div style={{
                  position: 'absolute', right: 0, top: '100%', marginTop: '4px', background: 'var(--bg-card)',
                  border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '8px 0',
                  zIndex: 100, minWidth: '160px', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}>
                  {INST_COL_DEFS.map(c => (
                    <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontSize: '12px', color: 'var(--text)', cursor: 'pointer', userSelect: 'none' }}
                      onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={iCol(c.id)} onChange={() => toggleInstCol(c.id)} style={{ accentColor: 'var(--blue)' }} />
                      {c.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Totals row above table */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', flexWrap: 'wrap' }}>
            {totalInvested > 0 && (
              <div style={{ padding: '6px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.4px' }}>Total Invested</div>
                <div style={{ fontSize: '14px', fontWeight: 600 }}>{formatINR(totalInvested)}</div>
              </div>
            )}
            {totalIntEarned > 0 && (
              <div style={{ padding: '6px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--green)', fontWeight: 600, letterSpacing: '0.4px' }}>Interest Earned</div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(totalIntEarned)}</div>
              </div>
            )}
            {totalIntProjected > 0 && (
              <div style={{ padding: '6px 12px', background: 'rgba(59,130,246,0.06)', borderRadius: 6, border: '1px solid rgba(59,130,246,0.15)' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--blue)', fontWeight: 600, letterSpacing: '0.4px' }}>Interest Projected</div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(totalIntProjected)}</div>
              </div>
            )}
          </div>

          <div style={{
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            overflow: 'auto', width: 'fit-content', maxWidth: '100%',
          }}>
            <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  {iCol('month')    && <th style={heldTh}>#</th>}
                  {iCol('date')     && <th style={heldTh}>Date</th>}
                  {iCol('invested') && <th style={{ ...heldTh, textAlign: 'right' }}>Invested</th>}
                  {iCol('earned')   && <th style={{ ...heldTh, textAlign: 'right' }}>Interest Earned</th>}
                  {iCol('projected')&& <th style={{ ...heldTh, textAlign: 'right' }}>Interest Projected</th>}
                </tr>
              </thead>
              <tbody>
                {installments.map((inst, i) => {
                  const isPast = inst.is_past;
                  const hasInterest = inst.interest_earned > 0 || inst.interest_projected > 0;
                  const pastBg = 'rgba(34,197,94,0.06)';
                  const futureBg = 'rgba(59,130,246,0.04)';
                  const pastBorder = '#22c55e';
                  const futureBorder = '#3b82f6';
                  return (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: isPast ? pastBg : futureBg,
                      borderLeft: `3px solid ${isPast ? pastBorder : futureBorder}`,
                      opacity: isPast ? 1 : 0.7,
                    }}>
                      {iCol('month')    && <td style={{ ...heldTd, color: 'var(--text-muted)', fontWeight: 600 }}>{inst.month}</td>}
                      {iCol('date')     && <td style={heldTd}>{formatDate(inst.date)}</td>}
                      {iCol('invested') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: inst.amount_invested > 0 ? 600 : 400, color: inst.amount_invested > 0 ? 'var(--text)' : 'var(--text-muted)' }}>
                        {inst.amount_invested > 0 ? formatINR(inst.amount_invested) : '-'}
                      </td>}
                      {iCol('earned') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600, color: inst.interest_earned > 0 ? 'var(--green)' : 'var(--text-muted)' }}>
                        {inst.interest_earned > 0 ? formatINR(inst.interest_earned) : '-'}
                      </td>}
                      {iCol('projected') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600, color: inst.interest_projected > 0 ? 'var(--blue)' : 'var(--text-muted)' }}>
                        {inst.interest_projected > 0 ? formatINR(inst.interest_projected) : '-'}
                      </td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Main Table ───────────────────────────────────── */
export default function FixedDepositTable({ deposits, loading, fdDashboard, onAddFD, onEditFD, onDeleteFD }) {
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

  // Filter + sort
  const q = searchTerm.trim().toLowerCase();
  let filtered = (deposits || []).filter(fd => {
    if (q) return (fd.name || '').toLowerCase().includes(q) || fd.bank.toLowerCase().includes(q) || (fd.remarks || '').toLowerCase().includes(q) || (fd.type || '').toLowerCase().includes(q);
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'bank':        va = a.name || a.bank; vb = b.name || b.bank; break;
      case 'type':        va = a.type || ''; vb = b.type || ''; break;
      case 'principal':   va = a.total_invested || a.principal; vb = b.total_invested || b.principal; break;
      case 'rate':        va = a.interest_rate; vb = b.interest_rate; break;
      case 'payout':      va = a.interest_payout || ''; vb = b.interest_payout || ''; break;
      case 'tenure':      va = a.tenure_months; vb = b.tenure_months; break;
      case 'startDate':   va = a.start_date; vb = b.start_date; break;
      case 'maturityDate':va = a.maturity_date; vb = b.maturity_date; break;
      case 'maturityAmt': va = a.maturity_amount; vb = b.maturity_amount; break;
      case 'interest':    va = a.interest_earned; vb = b.interest_earned; break;
      case 'interestProj':va = a.interest_projected || 0; vb = b.interest_projected || 0; break;
      case 'installments':va = a.installments_paid || 0; vb = b.installments_paid || 0; break;
      case 'tds':         va = a.tds; vb = b.tds; break;
      case 'status':      va = a.status; vb = b.status; break;
      default:            va = a.name || a.bank; vb = b.name || b.bank;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  const activeCount = (deposits || []).filter(d => d.status === 'Active').length;
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  if (loading && (deposits || []).length === 0) {
    return <div className="loading"><div className="spinner" />Loading fixed deposits...</div>;
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Fixed Deposits & MIS</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">{activeCount} active</span>
          <span className="section-badge" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            {(deposits || []).length} total
          </span>
        </div>
      </div>

      {/* Summary Bar */}
      {fdDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Invested</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(fdDashboard.total_invested)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity Value</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(fdDashboard.total_maturity_value)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Earned</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(fdDashboard.total_interest)}</div>
          </div>
          {fdDashboard.total_interest_projected > 0 && (
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Projected</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(fdDashboard.total_interest_projected)}</div>
            </div>
          )}
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{fdDashboard.active_count}</div>
          </div>
          {fdDashboard.maturing_soon > 0 && (
            <div style={{ flex: '1 1 80px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturing Soon</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--yellow)' }}>{fdDashboard.maturing_soon}</div>
            </div>
          )}
        </div>
      )}

      {/* Search + Column Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef} type="text" placeholder="Search by name, bank, type..."
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
                onClick={() => handleSort('bank')}>Name<SortIcon field="bank" /></th>
              {col('type') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('type')}>Type<SortIcon field="type" /></th>}
              {col('principal') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('principal')}>Principal<SortIcon field="principal" /></th>}
              {col('rate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('rate')}>Rate %<SortIcon field="rate" /></th>}
              {col('payout') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('payout')}>Payout<SortIcon field="payout" /></th>}
              {col('tenure') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('tenure')}>Tenure<SortIcon field="tenure" /></th>}
              {col('startDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('maturityDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityDate')}>Maturity<SortIcon field="maturityDate" /></th>}
              {col('maturityAmt') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityAmt')}>Maturity Amt<SortIcon field="maturityAmt" /></th>}
              {col('interest') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('interest')}>Interest<SortIcon field="interest" /></th>}
              {col('interestProj') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('interestProj')}>Projected<SortIcon field="interestProj" /></th>}
              {col('installments') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('installments')}>Paid<SortIcon field="installments" /></th>}
              {col('tds') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('tds')}>TDS<SortIcon field="tds" /></th>}
              {col('status') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('status')}>Status<SortIcon field="status" /></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={TOTAL_COLS} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {q ? 'No matching FDs found' : 'No fixed deposits yet. Click "+ Add FD" to add one.'}
              </td></tr>
            )}
            {filtered.map(fd => {
              const isExpanded = expandedId === fd.id;
              const sc = statusColor(fd.status);
              const tc = typeColor(fd.type);
              return (
                <React.Fragment key={fd.id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : fd.id)}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', background: isExpanded ? 'var(--bg-card-hover)' : 'transparent', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}>
                    <td style={{ padding: '10px 8px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text)' }}>
                        {fd.name || fd.bank}
                        {fd.days_to_maturity > 0 && fd.days_to_maturity <= 90 && fd.status === 'Active' && (
                          <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--yellow)', fontWeight: 400 }}>({fd.days_to_maturity}d left)</span>
                        )}
                      </div>
                      {fd.name && fd.name !== fd.bank && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{fd.bank}</div>
                      )}
                    </td>
                    {col('type') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: tc.bg, color: tc.color }}>{fd.type || 'FD'}</span>
                    </td>}
                    {col('principal') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(fd.total_invested || fd.principal)}</td>}
                    {col('rate') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{fd.interest_rate}%</td>}
                    {col('payout') && <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--text-dim)' }}>{fd.interest_payout || '-'}</td>}
                    {col('tenure') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{fd.tenure_months}m</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(fd.start_date)}</td>}
                    {col('maturityDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(fd.maturity_date)}</td>}
                    {col('maturityAmt') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--green)' }}>{formatINR(fd.maturity_amount)}</td>}
                    {col('interest') && <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--green)' }}>{formatINR(fd.interest_earned)}</td>}
                    {col('interestProj') && <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--blue)' }}>{formatINR(fd.interest_projected || 0)}</td>}
                    {col('installments') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{fd.installments_paid || 0}/{fd.installments_total || 0}</td>}
                    {col('tds') && <td style={{ padding: '10px 12px', textAlign: 'right', color: fd.tds > 0 ? 'var(--red)' : 'var(--text-muted)' }}>{formatINR(fd.tds)}</td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{fd.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <FDDetail fd={fd} onEdit={onEditFD} onDelete={onDeleteFD} />
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
