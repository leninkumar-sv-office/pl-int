import React from 'react';

const formatPrice = (price, type) => {
  if (!price || price === 0) return '--';
  if (type === 'forex') {
    return '₹' + price.toFixed(2);
  }
  if (type === 'commodity') {
    return '₹' + price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  // index
  return price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const ChangeLine = ({ label, pct }) => {
  if (!pct || pct === 0) return null;
  return (
    <span style={{ fontSize: '10px', color: pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
      {label}: {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
    </span>
  );
};

export default function MarketTicker({ tickers, loading }) {
  if (!tickers || tickers.length === 0) {
    if (loading) {
      return (
        <div style={styles.bar}>
          <div style={{ color: 'var(--text-muted)', fontSize: '12px', padding: '4px 0' }}>
            Loading market data...
          </div>
        </div>
      );
    }
    return null;
  }

  // Row 1: indices, Row 2: rest — use same column count so they align
  const INDEX_KEYS = new Set(['SENSEX', 'NIFTY50', 'SGX', 'NIKKEI', 'SGDINR', 'USDINR']);
  const row1 = tickers.filter((t) => INDEX_KEYS.has(t.key));
  const row2 = tickers.filter((t) => !INDEX_KEYS.has(t.key));
  const cols = Math.max(row1.length, row2.length);

  const renderItem = (t, idx, rowLen) => {
    const hasData = t.price > 0;
    const isLast = idx === rowLen - 1;
    const d = t.change_pct || 0;
    const w = t.week_change_pct || 0;
    const m = t.month_change_pct || 0;
    const priceColor = d >= 0 ? 'var(--green)' : 'var(--red)';
    return (
      <div key={t.key} style={{
        ...styles.item,
        borderRight: isLast ? 'none' : '1px solid var(--border)',
      }}>
        <span style={styles.label}>{t.label}{t.unit ? <span style={{ fontWeight: 400, opacity: 0.6, fontSize: '10px', marginLeft: '2px' }}>{t.unit.replace('₹', '')}</span> : null}</span>
        {hasData ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
              <span style={{ ...styles.price, color: priceColor }}>
                {formatPrice(t.price, t.type)}
              </span>
              {d !== 0 && (
                <span style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  color: d >= 0 ? 'var(--green)' : 'var(--red)',
                  background: d >= 0 ? 'rgba(0,210,106,0.12)' : 'rgba(255,71,87,0.12)',
                  padding: '1px 5px',
                  borderRadius: '3px',
                }}>
                  {d >= 0 ? '▲' : '▼'} {Math.abs(d).toFixed(2)}%
                </span>
              )}
            </div>
            {(w !== 0 || m !== 0) && (
              <div style={{ display: 'flex', gap: 8 }}>
                <ChangeLine label="7D" pct={w} />
                <ChangeLine label="1M" pct={m} />
              </div>
            )}
          </div>
        ) : (
          <span style={{ ...styles.price, color: 'var(--text-muted)' }}>--</span>
        )}
      </div>
    );
  };

  return (
    <div style={styles.bar}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {row1.map((t, i) => renderItem(t, i, row1.length))}
      </div>
      {row2.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${cols}, 1fr)`, borderTop: '1px solid var(--border)' }}>
          {row2.map((t, i) => renderItem(t, i, row2.length))}
        </div>
      )}
    </div>
  );
}

const styles = {
  bar: {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    padding: '8px 16px',
    marginBottom: '20px',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '6px 12px',
    whiteSpace: 'nowrap',
  },
  label: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.3px',
  },
  price: {
    fontSize: '14px',
    fontWeight: 700,
  },
};
