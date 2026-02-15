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
    case 'Closed': return { bg: 'var(--red-bg)', color: 'var(--red)' };
    default: return { bg: 'var(--yellow-bg)', color: 'var(--yellow)' };
  }
};

/* ── Main table column definitions ─────────────────────── */
const COL_DEFS = [
  { id: 'monthlyAmt',     label: 'Monthly Amt' },
  { id: 'rate',            label: 'Rate %' },
  { id: 'compounding',     label: 'Compounding' },
  { id: 'tenure',          label: 'Tenure' },
  { id: 'startDate',       label: 'Start Date' },
  { id: 'maturityDate',    label: 'Maturity Date' },
  { id: 'installments',    label: 'Installments' },
  { id: 'totalDeposited',  label: 'Total Deposited' },
  { id: 'interestAccrued', label: 'Interest Accrued' },
  { id: 'maturityAmt',     label: 'Maturity Value' },
  { id: 'status',          label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'rdVisibleCols_v2';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  const DEFAULT_HIDDEN = ['compounding'];
  return new Set(ALL_COL_IDS.filter(id => !DEFAULT_HIDDEN.includes(id)));
}

/* ── Installment sub-table column definitions ──────────── */
const INST_COL_DEFS = [
  { id: 'month',       label: '#' },
  { id: 'date',        label: 'Date' },
  { id: 'invested',    label: 'Amount Invested' },
  { id: 'earned',      label: 'Interest Earned' },
  { id: 'projected',   label: 'Interest Projected' },
  { id: 'cumulative',  label: 'Cumulative Interest' },
];
const INST_COL_LS_KEY = 'rdInstHiddenCols';

function loadInstHiddenCols() {
  try {
    const saved = localStorage.getItem(INST_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set();
}

/* ── Sub-table styles (matching stock/MF held lots) ─────── */
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

/* ── Compounding frequency label ──────────────────────── */
const compoundLabel = (freq) => {
  switch (freq) {
    case 1: return 'Monthly';
    case 2: return 'Bi-Monthly';
    case 3: return 'Quarterly';
    case 4: return 'Quarterly';
    case 6: return 'Half-Yearly';
    case 12: return 'Yearly';
    default: return freq ? `Every ${freq}m` : '-';
  }
};

/* ── RD Detail Row ───────────────────────────────── */
function RDDetail({ rd, onEdit, onDelete, onAddInstallment }) {
  const installments = rd.installments || [];

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
  const compoundMonths = installments.filter(i => i.is_compound_month);
  const totalInvested = installments.reduce((s, i) => s + (i.amount_invested || i.amount || 0), 0);
  const totalIntEarned = installments.reduce((s, i) => s + (i.interest_earned || 0), 0);
  const totalIntProjected = installments.reduce((s, i) => s + (i.interest_projected || 0), 0);
  const maxCumulativeInterest = Math.max(0, ...installments.map(i => i.cumulative_interest || 0));

  // Check if this is an xlsx-parsed RD (has detailed installments) vs manual (simple date/amount)
  const isDetailed = installments.length > 0 && installments[0].hasOwnProperty('interest_earned');

  return (
    <div style={{ background: 'var(--bg)', borderTop: '1px solid var(--border)', padding: '20px 24px' }}>
      {/* Actions */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>Actions:</span>
        {onAddInstallment && rd.status === 'Active' && rd.source === 'manual' && (
          <button className="btn btn-primary btn-sm" onClick={(e) => { e.stopPropagation(); onAddInstallment(rd); }}>+ Add Installment</button>
        )}
        {onEdit && rd.source === 'manual' && (
          <button className="btn btn-ghost btn-sm" onClick={(e) => { e.stopPropagation(); onEdit(rd); }}>Edit</button>
        )}
        {onDelete && rd.source === 'manual' && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--red)', borderColor: 'var(--red)' }}
            onClick={(e) => { e.stopPropagation(); if (window.confirm(`Delete RD "${rd.name || rd.bank}"?`)) onDelete(rd.id); }}>
            Delete
          </button>
        )}
        {rd.source === 'xlsx' && (
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
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{rd.name || `${rd.bank} RD`}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Bank</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{rd.bank}</div>
        </div>
        {rd.account_number && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Account No</div>
            <div style={{ fontSize: '15px', fontWeight: 600, fontFamily: 'monospace' }}>{rd.account_number}</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Monthly Amount</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(rd.monthly_amount)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Rate</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{rd.interest_rate}%</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Compounding</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{compoundLabel(rd.compounding_frequency)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Installments Paid</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{rd.installments_paid || 0} / {rd.installments_total || rd.tenure_months}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Deposited</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(rd.total_deposited)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Accrued</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(rd.total_interest_accrued || 0)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity Value</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(rd.maturity_amount)}</div>
        </div>
        {rd.days_to_maturity > 0 && rd.status === 'Active' && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Days Left</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: rd.days_to_maturity <= 90 ? 'var(--yellow)' : 'var(--text)' }}>{rd.days_to_maturity}d</div>
          </div>
        )}
        {rd.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{rd.remarks}</div>
          </div>
        )}
      </div>

      {/* Installment Schedule sub-table (xlsx-parsed detailed) */}
      {isDetailed && installments.length > 0 && (
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
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#f59e0b', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Compounding ({compoundMonths.length})</span>
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
                  zIndex: 100, minWidth: '180px', boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
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
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--blue)', fontWeight: 600, letterSpacing: '0.4px' }}>Interest to Earn</div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(totalIntProjected)}</div>
              </div>
            )}
            {maxCumulativeInterest > 0 && (
              <div style={{ padding: '6px 12px', background: 'rgba(245,158,11,0.06)', borderRadius: 6, border: '1px solid rgba(245,158,11,0.15)' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: '#f59e0b', fontWeight: 600, letterSpacing: '0.4px' }}>Cumulative Interest</div>
                <div style={{ fontSize: '14px', fontWeight: 600, color: '#f59e0b' }}>{formatINR(maxCumulativeInterest)}</div>
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
                  {iCol('month')      && <th style={heldTh}>#</th>}
                  {iCol('date')       && <th style={heldTh}>Date</th>}
                  {iCol('invested')   && <th style={{ ...heldTh, textAlign: 'right' }}>Invested</th>}
                  {iCol('earned')     && <th style={{ ...heldTh, textAlign: 'right' }}>Int Earned</th>}
                  {iCol('projected')  && <th style={{ ...heldTh, textAlign: 'right' }}>Int Projected</th>}
                  {iCol('cumulative') && <th style={{ ...heldTh, textAlign: 'right' }}>Cumulative Int</th>}
                </tr>
              </thead>
              <tbody>
                {installments.map((inst, i) => {
                  const isPast = inst.is_past;
                  const isCompound = inst.is_compound_month;
                  const pastBg = isCompound ? 'rgba(245,158,11,0.10)' : 'rgba(34,197,94,0.06)';
                  const futureBg = isCompound ? 'rgba(245,158,11,0.06)' : 'rgba(59,130,246,0.04)';
                  const pastBorder = isCompound ? '#f59e0b' : '#22c55e';
                  const futureBorder = isCompound ? '#f59e0b' : '#3b82f6';
                  return (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: isPast ? pastBg : futureBg,
                      borderLeft: `3px solid ${isPast ? pastBorder : futureBorder}`,
                      opacity: isPast ? 1 : 0.7,
                    }}>
                      {iCol('month') && <td style={{ ...heldTd, color: 'var(--text-muted)', fontWeight: 600 }}>
                        {inst.month}
                        {isCompound && (
                          <span style={{ marginLeft: '4px', fontSize: '9px', fontWeight: 700, padding: '1px 4px', borderRadius: '3px', background: 'rgba(245,158,11,0.15)', color: '#f59e0b', letterSpacing: '0.3px' }}>
                            Q
                          </span>
                        )}
                      </td>}
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
                      {iCol('cumulative') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: isCompound ? 700 : 400, color: inst.cumulative_interest > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                        {inst.cumulative_interest > 0 ? formatINR(inst.cumulative_interest) : '-'}
                      </td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Simple installment history (manual entries) */}
      {!isDetailed && installments.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' }}>
            Installment History ({installments.length})
          </div>
          <div style={{ border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }}>
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
                {installments.slice().sort((a, b) => (b.date || '').localeCompare(a.date || '')).map((inst, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                    <td style={{ ...heldTd, color: 'var(--text-muted)' }}>{installments.length - i}</td>
                    <td style={heldTd}>{formatDate(inst.date)}</td>
                    <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600 }}>{formatINR(inst.amount)}</td>
                    <td style={{ ...heldTd, color: 'var(--text-dim)' }}>{inst.remarks || '-'}</td>
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
export default function RecurringDepositTable({ deposits, loading, rdDashboard, onAddRD, onEditRD, onDeleteRD, onAddInstallment }) {
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
  let filtered = (deposits || []).filter(rd => {
    if (q) return (rd.name || '').toLowerCase().includes(q) || rd.bank.toLowerCase().includes(q) || (rd.account_number || '').includes(q) || (rd.remarks || '').toLowerCase().includes(q);
    return true;
  });

  filtered.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'bank':           va = a.name || a.bank; vb = b.name || b.bank; break;
      case 'monthlyAmt':     va = a.monthly_amount; vb = b.monthly_amount; break;
      case 'rate':           va = a.interest_rate; vb = b.interest_rate; break;
      case 'compounding':    va = a.compounding_frequency || 0; vb = b.compounding_frequency || 0; break;
      case 'tenure':         va = a.tenure_months; vb = b.tenure_months; break;
      case 'startDate':      va = a.start_date; vb = b.start_date; break;
      case 'maturityDate':   va = a.maturity_date; vb = b.maturity_date; break;
      case 'installments':   va = a.installments_paid || 0; vb = b.installments_paid || 0; break;
      case 'totalDeposited': va = a.total_deposited; vb = b.total_deposited; break;
      case 'interestAccrued':va = a.total_interest_accrued || 0; vb = b.total_interest_accrued || 0; break;
      case 'maturityAmt':    va = a.maturity_amount; vb = b.maturity_amount; break;
      case 'status':         va = a.status; vb = b.status; break;
      default:               va = a.name || a.bank; vb = b.name || b.bank;
    }
    if (typeof va === 'string') return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
    return sortDir === 'asc' ? (va || 0) - (vb || 0) : (vb || 0) - (va || 0);
  });

  const activeCount = (deposits || []).filter(d => d.status === 'Active').length;
  const TOTAL_COLS = 2 + COL_DEFS.filter(c => visibleCols.has(c.id)).length;

  if (loading && (deposits || []).length === 0) {
    return <div className="loading"><div className="spinner" />Loading recurring deposits...</div>;
  }

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Recurring Deposits</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">{activeCount} active</span>
          <span className="section-badge" style={{ background: 'var(--blue-bg)', color: 'var(--blue)' }}>
            {(deposits || []).length} total
          </span>
        </div>
      </div>

      {/* Summary Bar */}
      {rdDashboard && (
        <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', padding: '12px 16px', marginBottom: '12px', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Deposited</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(rdDashboard.total_deposited)}</div>
          </div>
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity Value</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{formatINR(rdDashboard.total_maturity_value)}</div>
          </div>
          {rdDashboard.total_interest_accrued > 0 && (
            <div style={{ flex: '1 1 120px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Accrued</div>
              <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(rdDashboard.total_interest_accrued)}</div>
            </div>
          )}
          <div style={{ flex: '1 1 120px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Monthly Commitment</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--blue)' }}>{formatINR(rdDashboard.monthly_commitment)}</div>
          </div>
          <div style={{ flex: '1 1 80px' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active RDs</div>
            <div style={{ fontSize: '16px', fontWeight: 600 }}>{rdDashboard.active_count}</div>
          </div>
        </div>
      )}

      {/* Search + Column Picker */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <div style={{ position: 'relative', flex: '1' }}>
          <input
            ref={searchRef} type="text" placeholder="Search by name, bank, account number..."
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
              {col('monthlyAmt') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('monthlyAmt')}>Monthly Amt<SortIcon field="monthlyAmt" /></th>}
              {col('rate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('rate')}>Rate %<SortIcon field="rate" /></th>}
              {col('compounding') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('compounding')}>Compound<SortIcon field="compounding" /></th>}
              {col('tenure') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('tenure')}>Tenure<SortIcon field="tenure" /></th>}
              {col('startDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('maturityDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityDate')}>Maturity<SortIcon field="maturityDate" /></th>}
              {col('installments') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('installments')}>Paid<SortIcon field="installments" /></th>}
              {col('totalDeposited') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('totalDeposited')}>Deposited<SortIcon field="totalDeposited" /></th>}
              {col('interestAccrued') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('interestAccrued')}>Interest<SortIcon field="interestAccrued" /></th>}
              {col('maturityAmt') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityAmt')}>Maturity<SortIcon field="maturityAmt" /></th>}
              {col('status') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('status')}>Status<SortIcon field="status" /></th>}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={TOTAL_COLS} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                {q ? 'No matching RDs found' : 'No recurring deposits yet. Click "+ Add RD" to add one.'}
              </td></tr>
            )}
            {filtered.map(rd => {
              const isExpanded = expandedId === rd.id;
              const sc = statusColor(rd.status);
              return (
                <React.Fragment key={rd.id}>
                  <tr onClick={() => setExpandedId(isExpanded ? null : rd.id)}
                    style={{ borderBottom: '1px solid var(--border)', cursor: 'pointer', background: isExpanded ? 'var(--bg-card-hover)' : 'transparent', transition: 'background 0.15s' }}
                    onMouseEnter={(e) => { if (!isExpanded) e.currentTarget.style.background = 'var(--bg-card-hover)'; }}
                    onMouseLeave={(e) => { if (!isExpanded) e.currentTarget.style.background = 'transparent'; }}>
                    <td style={{ padding: '10px 8px', textAlign: 'center', fontSize: '12px', color: 'var(--text-muted)' }}>
                      {isExpanded ? '\u25BC' : '\u25B6'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text)' }}>
                        {rd.name || rd.bank}
                        {rd.days_to_maturity > 0 && rd.days_to_maturity <= 90 && rd.status === 'Active' && (
                          <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--yellow)', fontWeight: 400 }}>({rd.days_to_maturity}d left)</span>
                        )}
                      </div>
                      {rd.account_number && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{rd.account_number}</div>
                      )}
                    </td>
                    {col('monthlyAmt') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(rd.monthly_amount)}</td>}
                    {col('rate') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{rd.interest_rate}%</td>}
                    {col('compounding') && <td style={{ padding: '10px 12px', textAlign: 'center', fontSize: '12px', color: 'var(--text-dim)' }}>{compoundLabel(rd.compounding_frequency)}</td>}
                    {col('tenure') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{rd.tenure_months}m</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(rd.start_date)}</td>}
                    {col('maturityDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(rd.maturity_date)}</td>}
                    {col('installments') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{rd.installments_paid || 0}/{rd.installments_total || rd.tenure_months}</td>}
                    {col('totalDeposited') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(rd.total_deposited)}</td>}
                    {col('interestAccrued') && <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--green)', fontWeight: 600 }}>{formatINR(rd.total_interest_accrued || 0)}</td>}
                    {col('maturityAmt') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--green)' }}>{formatINR(rd.maturity_amount)}</td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{rd.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <RDDetail rd={rd} onEdit={onEditRD} onDelete={onDeleteRD} onAddInstallment={onAddInstallment} />
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
