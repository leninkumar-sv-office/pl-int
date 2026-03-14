import React, { useState, useMemo, useRef, useEffect, useCallback } from 'react';
import { searchMFInstruments } from '../services/api';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function AddMFModal({ onAdd, onClose, initialData, funds }) {
  const [form, setForm] = useState({
    fund_code: initialData?.fund_code || '',
    fund_name: initialData?.name || initialData?.fund_name || '',
    units: '',
    nav: '',
    buy_date: new Date().toISOString().split('T')[0],
    remarks: '',
  });
  const [submitting, setSubmitting] = useState(false);

  // Search state for new fund
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [planFilter, setPlanFilter] = useState('direct');
  const [typeFilter, setTypeFilter] = useState('growth');
  const searchRef = useRef(null);
  const debounceRef = useRef(null);

  // Pre-filled from an existing fund row (read-only name)
  const isExistingFund = !!(initialData?.fund_code);

  const totalAmount = useMemo(() => {
    const u = parseFloat(form.units) || 0;
    const n = parseFloat(form.nav) || 0;
    return u * n;
  }, [form.units, form.nav]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleFundSelect = (e) => {
    const code = e.target.value;
    const found = funds?.find(f => f.fund_code === code);
    if (found) {
      setForm(prev => ({
        ...prev,
        fund_code: found.fund_code,
        fund_name: found.name,
        nav: found.current_nav > 0 ? String(found.current_nav) : '',
      }));
      setSearchQuery('');
      setSearchResults([]);
    } else {
      setForm(prev => ({ ...prev, fund_code: '', fund_name: '' }));
      setSearchQuery('');
    }
  };

  // Debounced search
  const doSearch = useCallback(async (q, plan, type) => {
    if (!q || q.length < 2) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }
    setSearching(true);
    try {
      const results = await searchMFInstruments(q, plan, type);
      setSearchResults(results || []);
      setShowResults(true);
    } catch (err) {
      console.error('MF search error:', err);
      setSearchResults([]);
    }
    setSearching(false);
  }, []);

  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    // Clear selection if user edits after picking
    if (form.fund_code) {
      setForm(prev => ({ ...prev, fund_code: '', fund_name: '' }));
    }
    // Debounce search
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => doSearch(val, planFilter, typeFilter), 300);
  };

  const handleFilterChange = (newPlan, newType) => {
    setPlanFilter(newPlan);
    setTypeFilter(newType);
    if (searchQuery.length >= 2) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      doSearch(searchQuery, newPlan, newType);
    }
  };

  const handlePickResult = (result) => {
    setForm(prev => ({
      ...prev,
      fund_code: result.tradingsymbol,
      fund_name: result.name,
      nav: result.last_price > 0 ? String(result.last_price) : prev.nav,
    }));
    setSearchQuery(result.name);
    setShowResults(false);
    setSearchResults([]);
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowResults(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.fund_name || !form.units || !form.nav || !form.buy_date) return;
    setSubmitting(true);
    await onAdd({
      ...form,
      units: parseFloat(form.units),
      nav: parseFloat(form.nav),
    });
    setSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Buy Mutual Fund</h2>
        <form onSubmit={handleSubmit}>

          {isExistingFund ? (
            <div className="form-group">
              <label>Fund Name</label>
              <input
                value={form.fund_name}
                disabled
                style={{ borderColor: 'var(--green)', opacity: 0.85 }}
              />
            </div>
          ) : (
            <>
              {funds && funds.length > 0 && (
                <div className="form-group">
                  <label>Select Existing Fund</label>
                  <select
                    value={form.fund_code}
                    onChange={handleFundSelect}
                    style={{ marginBottom: '8px' }}
                  >
                    <option value="">-- New Fund --</option>
                    {funds.map(f => (
                      <option key={f.fund_code} value={f.fund_code}>
                        {f.name.replace(/ - Direct Plan.*| - Direct Growth.*| Direct Growth.*/i, '')}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Search for new fund from Zerodha */}
              {!form.fund_code && (
                <div className="form-group" ref={searchRef} style={{ position: 'relative' }}>
                  <label>Search Fund *</label>
                  <div style={{ display: 'flex', gap: '6px', marginBottom: '8px' }}>
                    {[{ value: 'direct', label: 'Direct' }, { value: 'regular', label: 'Regular' }].map(opt => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => handleFilterChange(opt.value, typeFilter)}
                        style={{
                          padding: '3px 10px',
                          fontSize: '11px',
                          fontWeight: 600,
                          borderRadius: '12px',
                          border: '1px solid',
                          cursor: 'pointer',
                          borderColor: planFilter === opt.value ? 'var(--green)' : 'var(--border)',
                          background: planFilter === opt.value ? 'rgba(34,197,94,0.15)' : 'transparent',
                          color: planFilter === opt.value ? 'var(--green)' : 'var(--text-muted)',
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                    <span style={{ width: '1px', background: 'var(--border)', margin: '0 2px' }} />
                    {[{ value: 'growth', label: 'Growth' }, { value: 'dividend', label: 'IDCW' }, { value: '', label: 'All' }].map(opt => (
                      <button
                        key={opt.value}
                        type="button"
                        onClick={() => handleFilterChange(planFilter, opt.value)}
                        style={{
                          padding: '3px 10px',
                          fontSize: '11px',
                          fontWeight: 600,
                          borderRadius: '12px',
                          border: '1px solid',
                          cursor: 'pointer',
                          borderColor: typeFilter === opt.value ? '#3b82f6' : 'var(--border)',
                          background: typeFilter === opt.value ? 'rgba(59,130,246,0.15)' : 'transparent',
                          color: typeFilter === opt.value ? '#3b82f6' : 'var(--text-muted)',
                        }}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                  <input
                    value={searchQuery}
                    onChange={handleSearchChange}
                    onFocus={() => searchResults.length > 0 && setShowResults(true)}
                    placeholder="Type fund name e.g. SBI Gold Fund"
                    autoFocus={!isExistingFund}
                    autoComplete="off"
                  />
                  {searching && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Searching...
                    </div>
                  )}
                  {showResults && searchResults.length > 0 && (
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      maxHeight: '250px',
                      overflowY: 'auto',
                      zIndex: 100,
                      boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                    }}>
                      {searchResults.map((r, i) => (
                        <div
                          key={r.tradingsymbol || i}
                          onClick={() => handlePickResult(r)}
                          style={{
                            padding: '8px 12px',
                            cursor: 'pointer',
                            borderBottom: i < searchResults.length - 1 ? '1px solid var(--border)' : 'none',
                            fontSize: '13px',
                          }}
                          onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-input)'}
                          onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                        >
                          <div style={{ fontWeight: 500, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                            <span>{r.name}</span>
                            {r.plan && (
                              <span style={{
                                fontSize: '9px', fontWeight: 700, padding: '1px 5px', borderRadius: '3px',
                                color: r.plan.toLowerCase() === 'direct' ? '#22c55e' : '#f59e0b',
                                background: r.plan.toLowerCase() === 'direct' ? 'rgba(34,197,94,0.15)' : 'rgba(251,191,36,0.15)',
                                letterSpacing: '0.5px', textTransform: 'uppercase',
                              }}>
                                {r.plan}
                              </span>
                            )}
                            {r.scheme_type && (
                              <span style={{
                                fontSize: '9px', fontWeight: 700, padding: '1px 5px', borderRadius: '3px',
                                color: r.scheme_type.toLowerCase() === 'growth' ? '#3b82f6' : '#a855f7',
                                background: r.scheme_type.toLowerCase() === 'growth' ? 'rgba(59,130,246,0.15)' : 'rgba(168,85,247,0.15)',
                                letterSpacing: '0.5px', textTransform: 'uppercase',
                              }}>
                                {r.scheme_type}
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', gap: '12px', marginTop: '2px' }}>
                            <span>{r.tradingsymbol}</span>
                            <span>{r.amc}</span>
                            {r.last_price > 0 && <span style={{ color: 'var(--green)' }}>NAV: {formatINR(r.last_price)}</span>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                  {showResults && !searching && searchQuery.length >= 2 && searchResults.length === 0 && (
                    <div style={{
                      position: 'absolute',
                      top: '100%',
                      left: 0,
                      right: 0,
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '12px',
                      zIndex: 100,
                      fontSize: '12px',
                      color: 'var(--text-muted)',
                      textAlign: 'center',
                    }}>
                      No funds found
                    </div>
                  )}
                </div>
              )}

              {/* Show selected fund info */}
              {form.fund_code && (
                <div className="form-group">
                  <label>Selected Fund</label>
                  <div style={{
                    background: 'var(--bg-input)',
                    borderRadius: 'var(--radius-sm)',
                    padding: '10px 12px',
                    border: '1px solid var(--green)',
                  }}>
                    <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: '13px' }}>{form.fund_name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Code: {form.fund_code}
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setForm(prev => ({ ...prev, fund_code: '', fund_name: '' }));
                        setSearchQuery('');
                      }}
                      style={{
                        fontSize: '11px',
                        color: 'var(--red)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        marginTop: '4px',
                      }}
                    >
                      Change fund
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          <div className="form-row">
            <div className="form-group">
              <label>NAV ({'\u20B9'}) *</label>
              <input
                name="nav"
                type="number"
                step="any"
                min="0.01"
                value={form.nav}
                onChange={handleChange}
                placeholder="NAV per unit"
                required
              />
            </div>
            <div className="form-group">
              <label>Units *</label>
              <input
                name="units"
                type="number"
                step="any"
                min="0.001"
                value={form.units}
                onChange={handleChange}
                placeholder="Number of units"
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Buy Date *</label>
              <input
                name="buy_date"
                type="date"
                value={form.buy_date}
                onChange={handleChange}
                required
              />
            </div>
            <div className="form-group">
              <label>Remarks</label>
              <input
                name="remarks"
                value={form.remarks}
                onChange={handleChange}
                placeholder="Optional notes"
              />
            </div>
          </div>

          {/* Total Amount */}
          {totalAmount > 0 && (
            <div style={{
              background: 'var(--bg-input)',
              borderRadius: '8px',
              padding: '12px 16px',
              textAlign: 'center',
              marginTop: '8px',
            }}>
              <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginBottom: '4px' }}>Total Investment</div>
              <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)' }}>
                {formatINR(totalAmount)}
              </div>
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? 'Adding...' : '+ Buy MF'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
