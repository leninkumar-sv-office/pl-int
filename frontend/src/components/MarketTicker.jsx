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
    const isUp = t.change >= 0;
    const hasData = t.price > 0;
    const isLast = idx === rowLen - 1;
    return (
      <div key={t.key} style={{
        ...styles.item,
        borderRight: isLast ? 'none' : '1px solid var(--border)',
      }}>
        <span style={styles.label}>{t.label}{t.unit ? <span style={{ fontWeight: 400, opacity: 0.6, fontSize: '10px', marginLeft: '2px' }}>{t.unit.replace('₹', '')}</span> : null}</span>
        {hasData ? (
          <>
            <span style={{ ...styles.price, color: isUp ? 'var(--green)' : 'var(--red)' }}>
              {formatPrice(t.price, t.type)}
            </span>
            <span style={{
              ...styles.change,
              color: isUp ? 'var(--green)' : 'var(--red)',
              background: isUp ? 'rgba(0,210,106,0.12)' : 'rgba(255,71,87,0.12)',
            }}>
              {isUp ? '▲' : '▼'} {Math.abs(t.change_pct).toFixed(2)}%
            </span>
          </>
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
  change: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 6px',
    borderRadius: '4px',
  },
};
