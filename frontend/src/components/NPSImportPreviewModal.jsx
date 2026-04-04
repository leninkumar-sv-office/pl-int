import React, { useState } from 'react';
import useEscapeKey from '../hooks/useEscapeKey';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const formatDate = (dateStr) => {
  if (!dateStr) return '--';
  const d = new Date(dateStr + 'T00:00:00');
  if (isNaN(d.getTime())) return dateStr;
  const dd = String(d.getDate()).padStart(2, '0');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${dd}-${months[d.getMonth()]}-${d.getFullYear()}`;
};

const thStyle = { padding: '6px 10px', fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.5px' };
const tdStyle = { padding: '7px 10px', fontSize: '12px', color: 'var(--text)' };
const dupRowBg = 'rgba(251,191,36,0.10)';
const newRowBg = 'rgba(34,197,94,0.06)';

const schemeLabel = (code) => {
  switch (code) {
    case 'E': return 'Equity';
    case 'C': return 'Corporate';
    case 'G': return 'Govt Sec';
    default: return code;
  }
};
const schemeColor = (code) => {
  switch (code) {
    case 'E': return '#3b82f6';
    case 'C': return '#f59e0b';
    case 'G': return '#22c55e';
    default: return 'var(--text)';
  }
};

export default function NPSImportPreviewModal({ data, onConfirm, onCancel, isMultiPdf, fileCount }) {
  useEscapeKey(onCancel);
  const [confirming, setConfirming] = useState(false);
  const [hideDuplicates, setHideDuplicates] = useState(false);

  if (!data) return null;

  const { subscriber_info, transactions, contributions, summary } = data;
  const info = subscriber_info || {};

  const newTxns = transactions.filter(t => !t.isDuplicate);
  const dupTxns = transactions.filter(t => t.isDuplicate);
  const displayTxns = hideDuplicates ? newTxns : transactions;

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      await onConfirm();
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', justifyContent: 'center', alignItems: 'flex-start', paddingTop: '40px', overflow: 'auto' }}>
      <div style={{ background: 'var(--bg-card)', borderRadius: 12, width: '90%', maxWidth: '1000px', maxHeight: '90vh', overflow: 'auto', border: '1px solid var(--border)' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', position: 'sticky', top: 0, background: 'var(--bg-card)', zIndex: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px' }}>
                NPS Statement Preview
                {isMultiPdf && <span style={{ marginLeft: '8px', padding: '2px 8px', borderRadius: '10px', fontSize: '11px', background: 'var(--blue-bg)', color: 'var(--blue)' }}>{fileCount} PDFs</span>}
              </h3>
              {info.pran && <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>PRAN: {info.pran} | {info.subscriber_name || ''} | {info.scheme_preference || ''}</div>}
            </div>
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: 'rgba(34,197,94,0.1)', color: '#22c55e' }}>
                {summary?.new || 0} New
              </span>
              {(summary?.duplicates || 0) > 0 && (
                <span style={{ padding: '4px 10px', borderRadius: '12px', fontSize: '12px', fontWeight: 600, background: 'rgba(251,191,36,0.1)', color: '#f59e0b' }}>
                  {summary.duplicates} Duplicates
                </span>
              )}
              <label style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <input type="checkbox" checked={hideDuplicates} onChange={(e) => setHideDuplicates(e.target.checked)} />
                Hide duplicates
              </label>
            </div>
          </div>
        </div>

        <div style={{ padding: '16px 24px' }}>
          {/* Contributions summary */}
          {contributions && contributions.length > 0 && (
            <div style={{ marginBottom: '16px', padding: '10px 14px', background: 'rgba(34,197,94,0.06)', borderRadius: 8, border: '1px solid rgba(34,197,94,0.15)' }}>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', color: 'var(--green)', fontWeight: 600, marginBottom: '4px' }}>
                Contributions: {contributions.length}
              </div>
              <div style={{ fontSize: '14px', fontWeight: 600 }}>
                Total: {formatINR(contributions.reduce((s, c) => s + (c.amount || 0), 0))}
              </div>
            </div>
          )}

          {/* Transaction table */}
          <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
            Scheme Transactions ({displayTxns.length})
          </div>
          <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'auto', maxHeight: '50vh' }}>
            <table style={{ borderCollapse: 'collapse', width: '100%', whiteSpace: 'nowrap' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)', position: 'sticky', top: 0, zIndex: 5 }}>
                  <th style={thStyle}>Date</th>
                  <th style={thStyle}>Scheme</th>
                  <th style={thStyle}>Description</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Amount</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>NAV</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Units</th>
                  <th style={{ ...thStyle, textAlign: 'center' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {displayTxns.map((t, i) => {
                  const isDup = t.isDuplicate;
                  return (
                    <tr key={i} style={{ borderTop: '1px solid var(--border)', background: isDup ? dupRowBg : newRowBg, opacity: isDup ? 0.6 : 1 }}>
                      <td style={tdStyle}>{formatDate(t.date)}</td>
                      <td style={tdStyle}>
                        <span style={{ fontWeight: 600, color: schemeColor(t.scheme) }}>{t.scheme}</span>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)', marginLeft: '4px' }}>{schemeLabel(t.scheme)}</span>
                      </td>
                      <td style={{ ...tdStyle, maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.description}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', fontWeight: 600, color: t.amount < 0 ? 'var(--red)' : 'var(--text)' }}>{formatINR(Math.abs(t.amount))}</td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>{t.nav?.toFixed(4) || '--'}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', color: t.units < 0 ? 'var(--red)' : 'var(--text)' }}>{t.units?.toFixed(4) || '--'}</td>
                      <td style={{ ...tdStyle, textAlign: 'center' }}>
                        {isDup
                          ? <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '8px', background: 'rgba(251,191,36,0.2)', color: '#f59e0b', fontWeight: 600 }}>DUP</span>
                          : <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '8px', background: 'rgba(34,197,94,0.2)', color: '#22c55e', fontWeight: 600 }}>NEW</span>
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', position: 'sticky', bottom: 0, background: 'var(--bg-card)' }}>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {(summary?.duplicates || 0) > 0 && <span style={{ color: '#f59e0b' }}>({summary.duplicates} duplicates will be skipped)</span>}
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={onCancel} className="btn btn-ghost">Cancel</button>
            <button
              onClick={handleConfirm}
              disabled={confirming || (summary?.new || 0) === 0}
              className="btn btn-primary"
              style={{ background: '#22c55e', borderColor: '#22c55e', color: '#fff', fontWeight: 600, padding: '8px 20px', borderRadius: '8px', cursor: confirming ? 'wait' : 'pointer', opacity: (summary?.new || 0) === 0 ? 0.5 : 1 }}
            >
              {confirming ? 'Importing...' : `Confirm Import (${summary?.new || 0} transactions)`}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
