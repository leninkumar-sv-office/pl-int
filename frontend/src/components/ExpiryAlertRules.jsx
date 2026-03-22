import React, { useState, useEffect, useCallback } from 'react';
import { getExpiryRules, saveExpiryRule, deleteExpiryRule } from '../services/api';

const RULE_OPTIONS = {
  fd: [
    { type: 'days_before_maturity', label: 'Alert days before maturity', needsDays: true },
    { type: 'on_maturity', label: 'Alert on maturity day', needsDays: false },
  ],
  rd: [
    { type: 'days_before_maturity', label: 'Alert days before maturity', needsDays: true },
    { type: 'on_maturity', label: 'Alert on maturity day', needsDays: false },
  ],
  ppf: [
    { type: 'days_before_maturity', label: 'Alert days before maturity', needsDays: true },
    { type: 'on_maturity', label: 'Alert on maturity day', needsDays: false },
  ],
  nps: [
    { type: 'contribution_reminder', label: 'Monthly contribution reminder', needsDays: false },
  ],
  si: [
    { type: 'days_before_expiry', label: 'Alert days before expiry', needsDays: true },
    { type: 'on_expiry', label: 'Alert on expiry day', needsDays: false },
  ],
  insurance: [
    { type: 'days_before_expiry', label: 'Alert days before expiry', needsDays: true },
    { type: 'on_expiry', label: 'Alert on expiry day', needsDays: false },
  ],
  stocks: [
    { type: 'profit_threshold', label: 'Lot profit exceeds %', needsPct: true, needsTime: true },
    { type: 'day_drop_threshold', label: '1D price drop exceeds %', needsPct: true, needsTime: true },
    { type: 'week_drop_threshold', label: '1W price drop exceeds %', needsPct: true, needsTime: true },
    { type: 'month_drop_threshold', label: '1M price drop exceeds %', needsPct: true, needsTime: true },
    { type: 'near_52w_high', label: 'At or crossed 52-week high', needsTime: true },
    { type: 'near_52w_low', label: 'At or hit 52-week low', needsTime: true },
  ],
  mf: [
    { type: 'profit_threshold', label: 'Unit profit exceeds %', needsPct: true, needsTime: true },
    { type: 'day_drop_threshold', label: '1D NAV drop exceeds %', needsPct: true, needsTime: true },
    { type: 'week_drop_threshold', label: '1W NAV drop exceeds %', needsPct: true, needsTime: true },
    { type: 'month_drop_threshold', label: '1M NAV drop exceeds %', needsPct: true, needsTime: true },
    { type: 'near_52w_high', label: 'At or crossed 52-week high', needsTime: true },
    { type: 'near_52w_low', label: 'At or hit 52-week low', needsTime: true },
  ],
};

const inputStyle = {
  padding: '4px 8px', fontSize: '12px',
  background: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--border)',
  borderRadius: '4px', outline: 'none',
};

export default function ExpiryAlertRules({ category }) {
  const [expanded, setExpanded] = useState(false);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newType, setNewType] = useState('');
  const [newDays, setNewDays] = useState(30);
  const [newPct, setNewPct] = useState('25');
  const [newTime, setNewTime] = useState('16:30');
  const [saving, setSaving] = useState(false);

  const options = RULE_OPTIONS[category] || [];

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getExpiryRules(category);
      setRules(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [category]);

  // Load rules on mount (for badge count) and when expanded
  useEffect(() => {
    loadRules();
  }, [loadRules]);

  useEffect(() => {
    if (expanded) loadRules();
  }, [expanded, loadRules]);

  const selectedOpt = newType ? options.find(o => o.type === newType) : null;

  const handleAdd = async () => {
    if (!newType) return;
    setSaving(true);
    try {
      const payload = {
        category,
        rule_type: newType,
        enabled: true,
      };
      if (selectedOpt?.needsDays) {
        payload.days = newDays;
      }
      if (selectedOpt?.needsPct) {
        const parsed = parseFloat(newPct);
        payload.threshold_pct = (parsed > 0) ? parsed : 25;
      }
      if (selectedOpt?.needsTime) {
        payload.alert_time = newTime;
      }
      const rule = await saveExpiryRule(payload);
      setRules(prev => [...prev, rule]);
      setAdding(false);
      setNewType('');
      setNewDays(30);
      setNewPct('25');
      setNewTime('16:30');
    } catch { /* ignore */ }
    setSaving(false);
  };

  const handleDelete = async (ruleId) => {
    try {
      await deleteExpiryRule(ruleId);
      setRules(prev => prev.filter(r => r.id !== ruleId));
    } catch { /* ignore */ }
  };

  const handleToggle = async (rule) => {
    try {
      const updated = await saveExpiryRule({ ...rule, enabled: !rule.enabled });
      setRules(prev => prev.map(r => r.id === updated.id ? updated : r));
    } catch { /* ignore */ }
  };

  const ruleLabel = (rule) => {
    const opt = options.find(o => o.type === rule.rule_type);
    const label = opt?.label || rule.rule_type;
    if (opt?.needsDays) return `${label}: ${rule.days}d`;
    if (opt?.needsPct) {
      const time = rule.alert_time || '16:30';
      return `${label}: ${rule.threshold_pct || 25}% @ ${time}`;
    }
    return label;
  };

  const ruleCount = rules.filter(r => r.enabled).length;

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', marginLeft: '8px' }}>
      <button
        onClick={(e) => { e.stopPropagation(); setExpanded(!expanded); }}
        style={{
          background: ruleCount > 0 ? 'rgba(0,210,106,0.1)' : 'rgba(255,255,255,0.05)',
          border: `1px solid ${ruleCount > 0 ? 'rgba(0,210,106,0.3)' : 'var(--border)'}`,
          borderRadius: '12px',
          padding: '2px 10px',
          fontSize: '11px',
          fontWeight: 600,
          color: ruleCount > 0 ? 'var(--green)' : 'var(--text-muted)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
        }}
        title="Manage alert rules"
      >
        &#x1F514; {ruleCount > 0 ? `${ruleCount} rule${ruleCount > 1 ? 's' : ''}` : 'Alerts'}
      </button>

      {expanded && (
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'absolute',
            top: '100%',
            right: 0,
            marginTop: '4px',
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            padding: '12px',
            minWidth: '280px',
            zIndex: 100,
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text)', textTransform: 'uppercase' }}>
              Alert Rules
            </span>
            <button onClick={() => setExpanded(false)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '14px' }}>
              &times;
            </button>
          </div>

          {loading ? (
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '8px 0' }}>Loading...</div>
          ) : (
            <>
              {/* Existing rules */}
              {rules.length === 0 && !adding && (
                <div style={{ fontSize: '12px', color: 'var(--text-dim)', padding: '8px 0' }}>
                  No alert rules configured.
                </div>
              )}
              {rules.map(rule => (
                <div key={rule.id} style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  padding: '6px 8px', marginBottom: '4px',
                  background: 'var(--bg)', borderRadius: '4px',
                  opacity: rule.enabled ? 1 : 0.5,
                }}>
                  <span style={{ fontSize: '12px', color: 'var(--text)', flex: 1 }}>
                    {ruleLabel(rule)}
                  </span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    <button onClick={() => handleToggle(rule)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        fontSize: '14px', padding: '0 2px',
                        color: rule.enabled ? 'var(--green)' : 'var(--text-muted)',
                      }}
                      title={rule.enabled ? 'Disable' : 'Enable'}
                    >
                      {rule.enabled ? '●' : '○'}
                    </button>
                    <button onClick={() => handleDelete(rule.id)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        fontSize: '14px', color: 'var(--red)', padding: '0 2px',
                      }}
                      title="Delete rule"
                    >
                      &times;
                    </button>
                  </div>
                </div>
              ))}

              {/* Add rule form */}
              {adding ? (
                <div style={{ marginTop: '8px', padding: '8px', background: 'var(--bg)', borderRadius: '4px' }}>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    style={{
                      width: '100%', padding: '6px 8px', fontSize: '12px', marginBottom: '6px',
                      background: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--border)',
                      borderRadius: '4px', outline: 'none',
                    }}
                  >
                    <option value="">Select rule type...</option>
                    {options.map(opt => (
                      <option key={opt.type} value={opt.type}>{opt.label}</option>
                    ))}
                  </select>
                  {/* Days input for expiry rules */}
                  {selectedOpt?.needsDays && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Days:</span>
                      <input
                        type="number"
                        value={newDays}
                        onChange={(e) => setNewDays(Number(e.target.value) || 30)}
                        min={1}
                        max={365}
                        style={{ ...inputStyle, width: '60px' }}
                      />
                    </div>
                  )}
                  {/* Threshold % input for profit rules */}
                  {selectedOpt?.needsPct && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Profit %:</span>
                      <input
                        type="number"
                        value={newPct}
                        onChange={(e) => setNewPct(e.target.value)}
                        min={0.0001}
                        max={500}
                        step="any"
                        style={{ ...inputStyle, width: '60px' }}
                      />
                    </div>
                  )}
                  {/* Alert time input for profit rules */}
                  {selectedOpt?.needsTime && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Alert at:</span>
                      <input
                        type="time"
                        value={newTime}
                        onChange={(e) => setNewTime(e.target.value)}
                        style={{ ...inputStyle, width: '100px' }}
                      />
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button onClick={handleAdd} disabled={!newType || saving}
                      style={{
                        flex: 1, padding: '6px', fontSize: '11px', fontWeight: 600,
                        background: 'var(--green)', color: '#000', border: 'none',
                        borderRadius: '4px', cursor: 'pointer', opacity: (!newType || saving) ? 0.5 : 1,
                      }}>
                      {saving ? 'Saving...' : 'Save'}
                    </button>
                    <button onClick={() => { setAdding(false); setNewType(''); }}
                      style={{
                        padding: '6px 12px', fontSize: '11px',
                        background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)',
                        borderRadius: '4px', cursor: 'pointer',
                      }}>
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <button onClick={() => setAdding(true)}
                  style={{
                    width: '100%', marginTop: '6px', padding: '6px', fontSize: '11px', fontWeight: 600,
                    background: 'transparent', color: 'var(--text-muted)', border: '1px dashed var(--border)',
                    borderRadius: '4px', cursor: 'pointer',
                  }}>
                  + Add Rule
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
