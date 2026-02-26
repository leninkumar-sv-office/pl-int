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

const sipFreqLabel = (freq) => {
  const f = (freq || 'monthly').toLowerCase();
  if (f.includes('month')) return 'Monthly';
  if (f.includes('quarter')) return 'Quarterly';
  if (f.includes('year') || f.includes('annual')) return 'Yearly';
  return freq || '-';
};

const isOneTime = (ppf) => ppf.sip_end_date && ppf.sip_end_date === ppf.start_date;

const paymentTypeLabel = (ppf) => {
  if (isOneTime(ppf)) return 'One-time';
  if (ppf.sip_amount > 0) return `SIP - ${sipFreqLabel(ppf.sip_frequency)}`;
  return '-';
};

const paymentTypeStyle = (ppf) => {
  if (isOneTime(ppf)) return { bg: 'rgba(168,85,247,0.12)', color: '#a855f7' };
  if (ppf.sip_amount > 0) return { bg: 'rgba(59,130,246,0.12)', color: '#3b82f6' };
  return { bg: 'var(--bg-input)', color: 'var(--text-muted)' };
};

/* ── Main table column definitions ─────────────────────── */
const COL_DEFS = [
  { id: 'bank',           label: 'Bank' },
  { id: 'type',           label: 'Type' },
  { id: 'sipAmount',      label: 'Amount' },
  { id: 'rate',           label: 'Rate %' },
  { id: 'tenure',         label: 'Tenure' },
  { id: 'startDate',      label: 'Start Date' },
  { id: 'maturityDate',   label: 'Maturity Date' },
  { id: 'installments',   label: 'Installments' },
  { id: 'totalDeposited', label: 'Total Deposited' },
  { id: 'interestAccrued',label: 'Interest Accrued' },
  { id: 'maturityAmt',    label: 'Maturity Value' },
  { id: 'withdrawable',   label: 'Withdrawable' },
  { id: 'status',         label: 'Status' },
];
const ALL_COL_IDS = COL_DEFS.map(c => c.id);
const LS_KEY = 'ppfVisibleCols_v3';

function loadVisibleCols() {
  try {
    const saved = localStorage.getItem(LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set(ALL_COL_IDS);
}

/* ── Installment sub-table column definitions ──────────── */
const INST_COL_DEFS = [
  { id: 'month',       label: '#' },
  { id: 'date',        label: 'Date' },
  { id: 'invested',    label: 'Amount Invested' },
  { id: 'earned',      label: 'Interest Earned' },
  { id: 'projected',   label: 'Interest Projected' },
  { id: 'cumulative',  label: 'Cumulative Interest' },
  { id: 'cumAmount',   label: 'Cumulative Amount' },
];
const INST_COL_LS_KEY = 'ppfInstHiddenCols';

function loadInstHiddenCols() {
  try {
    const saved = localStorage.getItem(INST_COL_LS_KEY);
    if (saved) { const arr = JSON.parse(saved); if (Array.isArray(arr)) return new Set(arr); }
  } catch (_) {}
  return new Set();
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

/* ── PPF Detail Row ──────────────────────────────── */
function PPFDetail({ ppf, onEdit, onDelete, onAddContribution, onRedeem }) {
  const sc = statusColor(ppf.status);
  const installments = ppf.installments || [];

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
  const freeMonths = installments.filter(i => i.lock_status === 'free');
  const partialMonths = installments.filter(i => i.lock_status === 'partial');
  const totalInvested = installments.reduce((s, i) => s + (i.amount_invested || 0), 0);
  const totalIntEarned = installments.reduce((s, i) => s + (i.interest_earned || 0), 0);
  const totalIntProjected = installments.reduce((s, i) => s + (i.interest_projected || 0), 0);
  const maxCumulativeInterest = Math.max(0, ...installments.map(i => i.cumulative_interest || 0));

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
        {onRedeem && ppf.status === 'Matured' && (
          <button className="btn btn-ghost btn-sm" style={{ color: 'var(--blue)', borderColor: 'var(--blue)' }}
            onClick={(e) => { e.stopPropagation(); onRedeem(ppf); }}>
            Redeem ({formatINR(ppf.withdrawable_amount)})
          </button>
        )}
        {ppf.withdrawal_status === 'partial' && ppf.withdrawable_amount > 0 && (
          <button className="btn btn-ghost btn-sm" style={{ color: '#f59e0b', borderColor: '#f59e0b' }}
            onClick={(e) => { e.stopPropagation(); window.alert(`Partial withdrawal available: ${formatINR(ppf.withdrawable_amount)}\n\n${ppf.withdrawal_note}\n\nVisit your bank/post office to initiate withdrawal.`); }}>
            Withdraw ({formatINR(ppf.withdrawable_amount)})
          </button>
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
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Payment Type</div>
          {(() => { const pts = paymentTypeStyle(ppf); return (
            <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: pts.bg, color: pts.color, marginTop: '2px' }}>{paymentTypeLabel(ppf)}</span>
          ); })()}
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>{isOneTime(ppf) ? 'Lump Sum' : 'SIP Amount'}</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(ppf.sip_amount)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Rate</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.interest_rate}%</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Compounding</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>Annually</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Installments Paid</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{ppf.installments_paid || 0} / {ppf.installments_total || ppf.tenure_months}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Deposited</div>
          <div style={{ fontSize: '15px', fontWeight: 600 }}>{formatINR(ppf.total_deposited)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Interest Accrued</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.total_interest_accrued || 0)}</div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Maturity Value</div>
          <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.maturity_amount)}</div>
        </div>
        {ppf.days_to_maturity > 0 && ppf.status === 'Active' && (
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Days Left</div>
            <div style={{ fontSize: '15px', fontWeight: 600, color: ppf.days_to_maturity <= 90 ? 'var(--yellow)' : 'var(--text)' }}>{ppf.days_to_maturity}d</div>
          </div>
        )}
        <div>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
          <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: sc.bg, color: sc.color }}>{ppf.status}</span>
        </div>
        {ppf.remarks && (
          <div style={{ flex: '1 1 100%' }}>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Remarks</div>
            <div style={{ fontSize: '13px', color: 'var(--text-dim)' }}>{ppf.remarks}</div>
          </div>
        )}
      </div>

      {/* Withdrawal Eligibility */}
      {ppf.withdrawal_status && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px', padding: '12px 16px',
          borderRadius: 'var(--radius-sm)', border: '1px solid',
          ...(ppf.withdrawal_status === 'full' ? {
            background: 'rgba(0,210,106,0.06)', borderColor: 'rgba(0,210,106,0.2)',
          } : ppf.withdrawal_status === 'partial' ? {
            background: 'rgba(245,158,11,0.06)', borderColor: 'rgba(245,158,11,0.2)',
          } : {
            background: 'rgba(255,255,255,0.02)', borderColor: 'var(--border)',
          }),
        }}>
          <div style={{ fontSize: '20px' }}>
            {ppf.withdrawal_status === 'full' ? '\u2705' : ppf.withdrawal_status === 'partial' ? '\u26A0\uFE0F' : '\uD83D\uDD12'}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '2px' }}>{ppf.withdrawal_note}</div>
            {ppf.withdrawable_amount > 0 && (
              <div style={{ fontSize: '16px', fontWeight: 700, color: ppf.withdrawal_status === 'full' ? 'var(--green)' : '#f59e0b' }}>
                Withdrawable: {formatINR(ppf.withdrawable_amount)}
              </div>
            )}
          </div>
        </div>
      )}

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
              <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#f59e0b', display: 'inline-block' }} />
                <span style={{ color: 'var(--text-muted)' }}>Compounding ({compoundMonths.length})</span>
              </span>
              {partialMonths.length > 0 && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#a855f7', display: 'inline-block' }} />
                  <span style={{ color: 'var(--text-muted)' }}>Partial Withdraw ({partialMonths.length})</span>
                </span>
              )}
              {freeMonths.length > 0 && (
                <span style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: '#06b6d4', display: 'inline-block' }} />
                  <span style={{ color: 'var(--text-muted)' }}>Free ({freeMonths.length})</span>
                </span>
              )}
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

          {/* Summary boxes */}
          <div style={{ display: 'flex', gap: '16px', marginBottom: '8px', flexWrap: 'wrap' }}>
            {totalInvested > 0 && (
              <div style={{ padding: '6px 12px', background: 'rgba(0,210,106,0.06)', borderRadius: 6, border: '1px solid rgba(0,210,106,0.15)' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-dim)', fontWeight: 600, letterSpacing: '0.4px' }}>Total Invested</div>
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
            <div style={{ padding: '6px 12px', background: 'rgba(168,85,247,0.06)', borderRadius: 6, border: '1px solid rgba(168,85,247,0.15)' }}>
              <div style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--purple, #a855f7)', fontWeight: 600, letterSpacing: '0.4px' }}>Max Yearly (80C)</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--purple, #a855f7)' }}>{'\u20B9'}1,50,000</div>
            </div>
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
                  {iCol('cumAmount')  && <th style={{ ...heldTh, textAlign: 'right' }}>Cumulative Amt</th>}
                </tr>
              </thead>
              <tbody>
                {installments.map((inst, i) => {
                  const isPast = inst.is_past;
                  const isCompound = inst.is_compound_month;
                  const lockStatus = inst.lock_status || 'locked';

                  // Background priority: compound > lock status > past/future
                  let bg, borderColor;
                  if (isCompound) {
                    bg = isPast ? 'rgba(245,158,11,0.10)' : 'rgba(245,158,11,0.06)';
                    borderColor = '#f59e0b';
                  } else if (lockStatus === 'free') {
                    bg = isPast ? 'rgba(6,182,212,0.10)' : 'rgba(6,182,212,0.05)';
                    borderColor = '#06b6d4';
                  } else if (lockStatus === 'partial') {
                    bg = isPast ? 'rgba(168,85,247,0.08)' : 'rgba(168,85,247,0.04)';
                    borderColor = '#a855f7';
                  } else {
                    bg = isPast ? 'rgba(34,197,94,0.06)' : 'rgba(59,130,246,0.04)';
                    borderColor = isPast ? '#22c55e' : '#3b82f6';
                  }

                  return (
                    <tr key={i} style={{
                      borderBottom: '1px solid var(--border)',
                      background: bg,
                      borderLeft: `3px solid ${borderColor}`,
                      opacity: isPast ? 1 : 0.7,
                    }}>
                      {iCol('month') && <td style={{ ...heldTd, color: 'var(--text-muted)', fontWeight: 600 }}>
                        {inst.month}
                        {isCompound && (
                          <span style={{ marginLeft: '4px', fontSize: '9px', fontWeight: 700, padding: '1px 4px', borderRadius: '3px', background: 'rgba(245,158,11,0.15)', color: '#f59e0b', letterSpacing: '0.3px' }}>
                            Y
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
                      {iCol('cumAmount') && <td style={{ ...heldTd, textAlign: 'right', fontWeight: 600, color: lockStatus === 'free' ? '#06b6d4' : lockStatus === 'partial' ? '#a855f7' : 'var(--text)' }}>
                        {formatINR(inst.cumulative_amount)}
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
export default function PPFTable({ accounts, loading, ppfDashboard, onAddPPF, onEditPPF, onDeletePPF, onAddContribution, onRedeemPPF }) {
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
      case 'type':           va = isOneTime(a) ? 0 : 1; vb = isOneTime(b) ? 0 : 1; break;
      case 'sipAmount':      va = a.sip_amount || 0; vb = b.sip_amount || 0; break;
      case 'rate':           va = a.interest_rate; vb = b.interest_rate; break;
      case 'tenure':         va = a.tenure_years || 0; vb = b.tenure_years || 0; break;
      case 'startDate':      va = a.start_date; vb = b.start_date; break;
      case 'maturityDate':   va = a.maturity_date; vb = b.maturity_date; break;
      case 'installments':   va = a.installments_paid || 0; vb = b.installments_paid || 0; break;
      case 'totalDeposited': va = a.total_deposited; vb = b.total_deposited; break;
      case 'interestAccrued':va = a.total_interest_accrued || 0; vb = b.total_interest_accrued || 0; break;
      case 'maturityAmt':    va = a.maturity_amount || 0; vb = b.maturity_amount || 0; break;
      case 'withdrawable':   va = a.withdrawable_amount || 0; vb = b.withdrawable_amount || 0; break;
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
              {col('type') && <th style={{ padding: '10px 12px', textAlign: 'center', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('type')}>Type<SortIcon field="type" /></th>}
              {col('sipAmount') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('sipAmount')}>Amount<SortIcon field="sipAmount" /></th>}
              {col('rate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('rate')}>Rate %<SortIcon field="rate" /></th>}
              {col('tenure') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('tenure')}>Tenure<SortIcon field="tenure" /></th>}
              {col('startDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('startDate')}>Start<SortIcon field="startDate" /></th>}
              {col('maturityDate') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityDate')}>Maturity<SortIcon field="maturityDate" /></th>}
              {col('installments') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('installments')}>Paid<SortIcon field="installments" /></th>}
              {col('totalDeposited') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('totalDeposited')}>Deposited<SortIcon field="totalDeposited" /></th>}
              {col('interestAccrued') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('interestAccrued')}>Interest<SortIcon field="interestAccrued" /></th>}
              {col('maturityAmt') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('maturityAmt')}>Maturity<SortIcon field="maturityAmt" /></th>}
              {col('withdrawable') && <th style={{ padding: '10px 12px', textAlign: 'right', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-dim)', fontWeight: 600, cursor: 'pointer' }} onClick={() => handleSort('withdrawable')}>Withdrawable<SortIcon field="withdrawable" /></th>}
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
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text)' }}>
                        {ppf.account_name}
                        {ppf.days_to_maturity > 0 && ppf.days_to_maturity <= 90 && ppf.status === 'Active' && (
                          <span style={{ marginLeft: '8px', fontSize: '11px', color: 'var(--yellow)', fontWeight: 400 }}>({ppf.days_to_maturity}d left)</span>
                        )}
                      </div>
                      {ppf.account_number && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'monospace' }}>{ppf.account_number}</div>
                      )}
                    </td>
                    {col('bank') && <td style={{ padding: '10px 12px', color: 'var(--text-dim)' }}>{ppf.bank}</td>}
                    {col('type') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      {(() => { const pts = paymentTypeStyle(ppf); return (
                        <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: pts.bg, color: pts.color }}>{paymentTypeLabel(ppf)}</span>
                      ); })()}
                    </td>}
                    {col('sipAmount') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(ppf.sip_amount)}</td>}
                    {col('rate') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{ppf.interest_rate}%</td>}
                    {col('tenure') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{ppf.tenure_years}y</td>}
                    {col('startDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(ppf.start_date)}</td>}
                    {col('maturityDate') && <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: '12px', color: 'var(--text-dim)' }}>{formatDate(ppf.maturity_date)}</td>}
                    {col('installments') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>{ppf.installments_paid || 0}/{ppf.installments_total || ppf.tenure_months}</td>}
                    {col('totalDeposited') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600 }}>{formatINR(ppf.total_deposited)}</td>}
                    {col('interestAccrued') && <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--green)', fontWeight: 600 }}>{formatINR(ppf.total_interest_accrued || 0)}</td>}
                    {col('maturityAmt') && <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--green)' }}>{formatINR(ppf.maturity_amount)}</td>}
                    {col('withdrawable') && <td style={{ padding: '10px 12px', textAlign: 'right' }}>
                      {ppf.withdrawable_amount > 0 ? (
                        <span style={{ fontWeight: 600, color: ppf.withdrawal_status === 'full' ? 'var(--green)' : '#f59e0b' }}>{formatINR(ppf.withdrawable_amount)}</span>
                      ) : (
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Locked</span>
                      )}
                    </td>}
                    {col('status') && <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                      <span style={{ display: 'inline-block', padding: '2px 10px', borderRadius: '12px', fontSize: '11px', fontWeight: 600, background: sc.bg, color: sc.color }}>{ppf.status}</span>
                    </td>}
                  </tr>
                  {isExpanded && (
                    <tr><td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                      <PPFDetail ppf={ppf} onEdit={onEditPPF} onDelete={onDeletePPF} onAddContribution={onAddContribution} onRedeem={onRedeemPPF} />
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
