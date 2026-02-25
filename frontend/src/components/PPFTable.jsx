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
    default: return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
  }
};

/* ── Main table column definitions ─────────────────────── */
const COL_DEFS = [
  { id: 'bank',           label: 'Bank' },
  { id: 'rate',           label: 'Rate %' },
  { id: 'startDate',      label: 'Start Date' },
  { id: 'maturityDate',   label: 'Maturity Date' },
  { id: 'yearsCompleted', label: 'Years' },
  { id: 'totalDeposited', label: 'Total Deposited' },
  { id: 'totalInterest',  label: 'Interest Earned' },
  { id: 'currentBalance', label: 'Current Balance' },
  { id: 'status',         label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'ppfVisibleCols_v1';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(ALL_COL_IDS);
}

/* ── Yearly schedule sub-table styles ─────────────────── */
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

/* ── Yearly schedule column definitions ───────────────── */
const SCHED_COL_DEFS = [
  { id: 'year',     label: 'Year' },
  { id: 'fy',       label: 'Financial Year' },
  { id: 'opening',  label: 'Opening Balance' },
  { id: 'deposit',  label: 'Deposit' },
  { id: 'interest', label: 'Interest Earned' },
  { id: 'closing',  label: 'Closing Balance' },
];
const SCHED_COL_LS_KEY = 'ppfSchedHiddenCols';

function loadSchedHiddenCols() {
  try {
    const saved = localStorage.getItem(SCHED_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set();
}

/* ── PPF Detail Row ──────────────────────────────── */
function PPFDetail({ ppf, onEdit, onDelete, onAddContribution }) {
  const sc = statusColor(ppf.status);
  const schedule = ppf.yearly_schedule || [];
  const contributions = ppf.contributions || [];

  // Schedule column visibility
  const [hiddenSchedCols, setHiddenSchedCols] = useState(loadSchedHiddenCols);
  const [showColPicker, setShowColPicker] = useState(false);
  const colPickerRef = useRef(null);
  const sCol = (id) => !hiddenSchedCols.has(id);

  const toggleSchedCol = (id) => {
    setHiddenSchedCols(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      try { localStorage.setItem(SCHED_COL_LS_KEY, JSON.stringify([...next])); } catch (_) {}
      return next;
    });
  };

  useEffect(() => {
    if (!showColPicker) return;
    const handler = (e) => { if (colPickerRef.current && !colPickerRef.current.contains(e.target)) setShowColPicker(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showColPicker]);

  const pastYears = schedule.filter(y => y.is_past);
  const futureYears = schedule.filter(y => !y.is_past);

  return (
    <div style={{ background: 'var(--bg)', borderTop: '1px solid var(--border)', padding: '20px 24px' }}>
      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>Actions:</span>
        {onAddContribution && ppf.status === 'Active' && (
          <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); onAddContribution(ppf); }}>+ Add Contribution</button>
        )}
        {onEdit && (
          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(ppf); }}>Edit</button>
        )}
        {onDelete && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete PPF account "${ppf.account_name}"?`)) onDelete(ppf.id); }}>
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
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.account_name}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bank</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.bank}</div>
        </div>
        {ppf.account_number && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Account No</div>
            <div style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'monospace' }}>{ppf.account_number}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Rate</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.interest_rate}%</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Tenure</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.tenure_years || 15} years</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Start</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(ppf.start_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatDate(ppf.maturity_date)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Years Completed</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.years_completed || 0} / {ppf.tenure_years || 15}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Deposited</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(ppf.total_deposited)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Earned</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.total_interest_earned)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Balance</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.current_balance)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: sc.bg, color: sc.color }}>{ppf.status}</span>
        </div>
        {ppf.days_to_maturity > 0 && ppf.status === 'Active' && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Days to Maturity</div>
            <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.days_to_maturity}d</div>
          </div>
        )}
        {ppf.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{ppf.remarks}</div>
          </div>
        )}
      </div>

      {/* Yearly Schedule sub-table */}
      {schedule.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span>Yearly Schedule ({schedule.length})</span>
            <span style={{ display: 'flex', gap: '8px', fontSize: '10px', fontWeight: 500 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#22c55e', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Past ({pastYears.length})</span>
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#3b82f6', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Future ({futureYears.length})</span>
              </span>
            </span>
            {/* Column picker */}
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
                  zIndex: 100, minWidth: '170px', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                }}>
                  {SCHED_COL_DEFS.map(c => (
                    <label key={c.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 12px', fontSize: '12px', color: 'var(--text)', cursor: 'pointer', userSelect: 'none' }}
                      onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" checked={sCol(c.id)} onChange={() => toggleSchedCol(c.id)} style={{ accentColor: 'var(--blue)' }} />
                      {c.label}
                    </label>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Summary boxes */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <div style={{ padding: '6px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600, letterSpacing: '0.4px' }}>Total Deposited</div>
              <div style={{ fontSize: '14px', fontWeight: 600 }}>{formatINR(ppf.total_deposited)}</div>
            </div>
            <div style={{ padding: '6px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--green)', fontWeight: 600, letterSpacing: '0.4px' }}>Total Interest</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.total_interest_earned)}</div>
            </div>
            <div style={{ padding: '6px 12px', background: 'rgba(59,130,246,0.06)', borderRadius: 6, border: '1px solid rgba(59,130,246,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--blue)', fontWeight: 600, letterSpacing: '0.4px' }}>Current Balance</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(ppf.current_balance)}</div>
            </div>
            <div style={{ padding: '6px 12px', background: 'rgba(168,85,247,0.06)', borderRadius: 6, border: '1px solid rgba(168,85,247,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--purple, #a855f7)', fontWeight: 600, letterSpacing: '0.4px' }}>Max Yearly (80C)</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--purple, #a855f7)' }}>₹1,50,000</div>
            </div>
          </div>

          <div style={{
            border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)',
            overflow: 'auto', width: 'fit-content', maxWidth: '100%',
          }}>
            <table style={{ borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  {sCol('year')     && <th style={heldTh}>Year</th>}
                  {sCol('fy')       && <th style={heldTh}>Financial Year</th>}
                  {sCol('opening')  && <th style={{ ...heldTh, textAlign: 'right' }}>Opening</th>}
                  {sCol('deposit')  && <th style={{ ...heldTh, textAlign: 'right' }}>Deposit</th>}
                  {sCol('interest') && <th style={{ ...heldTh, textAlign: 'right' }}>Interest</th>}
                  {sCol('closing')  && <th style={{ ...heldTh, textAlign: 'right' }}>Closing</th>}
                </tr>
              </thead>
              <tbody>
                {schedule.map((yr, i) => {
                  const isPast = yr.is_past;
                  const hasDeposit = yr.deposit > 0;
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
                      {sCol('year')     && <td style={{ ...heldTd, fontWeight: 600, color: 'var(--text-muted)' }}>{yr.year}</td>}
                      {sCol('fy')       && <td style={{ ...heldTd, fontWeight: 600 }}>FY {yr.financial_year}</td>}
                      {sCol('opening')  && <td style={{ ...heldTd, textAlign: 'right' }}>{formatINR(yr.opening_balance)}</td>}
                      {sCol('deposit')  && <td style={{ ...heldTd, textAlign: 'right', fontWeight: hasDeposit ? 600 : 400, color: hasDeposit ? 'var(--text)' : 'var(--text-muted)' }}>
                        {hasDeposit ? formatINR(yr.deposit) : '-'}
                      </td>}
                      {sCol('interest') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600, color: yr.interest_earned > 0 ? 'var(--green)' : 'var(--text-muted)' }}>
                        {yr.interest_earned > 0 ? formatINR(yr.interest_earned) : '-'}
                      </td>}
                      {sCol('closing')  && <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600 }}>{formatINR(yr.closing_balance)}</td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

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
export default function PPFTable({ accounts, loading, ppfDashboard, onAddPPF, onEditPPF, onDeletePPF, onAddContribution }) {
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
  let filtered = (accounts || []).filter(ppf => {
    if (q) return ppf.account_name.toLowerCase().includes(q) || ppf.bank.toLowerCase().includes(q) || (ppf.account_number || '').includes(q);
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'account_name':   va = a.account_name; vb = b.account_name; break;
      case 'bank':           va = a.bank; vb = b.bank; break;
      case 'rate':           va = a.interest_rate; vb = b.interest_rate; break;
      case 'startDate':      va = a.start_date; vb = b.start_date; break;
      case 'maturityDate':   va = a.maturity_date; vb = b.maturity_date; break;
      case 'yearsCompleted': va = a.years_completed || 0; vb = b.years_completed || 0; break;
      case 'totalDeposited': va = a.total_deposited; vb = b.total_deposited; break;
      case 'totalInterest':  va = a.total_interest_earned || 0; vb = b.total_interest_earned || 0; break;
      case 'currentBalance': va = a.current_balance || 0; vb = b.current_balance || 0; break;
      case 'status':         va = a.status; vb = b.status; break;
      default:               va = a.account_name; vb = b.account_name;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  const activeCount = (accounts || []).filter(a => a.status === 'Active').length;
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  if (loading && (accounts || []).length === 0) {
    return <div className="loading"><div className="spinner" />Loading PPF accounts...</div>;
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Public Provident Fund (PPF)</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">{activeCount} active</span>
          <span className="section-badge" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            {(accounts || []).length} total
          </span>
        </div>
      </div>

      {/* Summary Bar */}
      {ppfDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Deposited</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(ppfDashboard.total_deposited)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Interest</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppfDashboard.total_interest)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Current Balance</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(ppfDashboard.current_balance)}</div>
          </div>
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{ppfDashboard.active_count}</div>
          </div>
        </div>
      )}

      {/* Search + Column Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef} type="text" placeholder="Search by account name or bank..."
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
              {col('bank') && <th style={{ padding: '10px 12px', textAlign: 'left', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('bank')}>Bank<SortIcon field="bank" /></th>}
              {col('rate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('rate')}>Rate %<SortIcon field="rate" /></th>}
              {col('startDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('maturityDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityDate')}>Maturity<SortIcon field="maturityDate" /></th>}
              {col('yearsCompleted') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('yearsCompleted')}>Years<SortIcon field="yearsCompleted" /></th>}
              {col('totalDeposited') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('totalDeposited')}>Deposited<SortIcon field="totalDeposited" /></th>}
              {col('totalInterest') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('totalInterest')}>Interest<SortIcon field="totalInterest" /></th>}
              {col('currentBalance') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('currentBalance')}>Balance<SortIcon field="currentBalance" /></th>}
              {col('status') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('status')}>Status<SortIcon field="status" /></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={TOTAL_COLS} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {q ? 'No matching PPF accounts found' : 'No PPF accounts yet. Click "+ Add PPF" to add one.'}
              </td></tr>
            )}
            {filtered.map(ppf => {
              const isExpanded = expandedId === ppf.id;
              const sc = statusColor(ppf.status);
              return (
                <React.Fragment key={ppf.id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : ppf.id)}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', background: isExpanded ? 'var(--bg-card-hover)' : 'transparent', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}>
                    <td style={{ padding: '10px 8px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </td>
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: 'var(--text)' }}>
                      {ppf.account_name}
                      {ppf.account_number && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace', fontWeight: 400 }}>{ppf.account_number}</div>
                      )}
                    </td>
                    {col('bank') && <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>{ppf.bank}</td>}
                    {col('rate') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{ppf.interest_rate}%</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(ppf.start_date)}</td>}
                    {col('maturityDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(ppf.maturity_date)}</td>}
                    {col('yearsCompleted') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{ppf.years_completed || 0}/{ppf.tenure_years || 15}</td>}
                    {col('totalDeposited') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(ppf.total_deposited)}</td>}
                    {col('totalInterest') && <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--green)', fontWeight: 600 }}>{formatINR(ppf.total_interest_earned)}</td>}
                    {col('currentBalance') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(ppf.current_balance)}</td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{ppf.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <PPFDetail ppf={ppf} onEdit={onEditPPF} onDelete={onDeletePPF} onAddContribution={onAddContribution} />
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
