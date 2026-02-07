import React from 'react';

const formatPrice = (price, type) => {
  if (!price || price === 0) return '--';
  if (type === 'forex') {
    return '₹' + price.toFixed(2);
  }
  if (type === 'commodity') {
    return '$' + price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

  return (
    <div style={styles.bar}>
      <div style={styles.track}>
        {tickers.map((t) => {
          const isUp = t.change >= 0;
          const hasData = t.price > 0;
          return (
            <div key={t.key} style={styles.item}>
              <span style={styles.label}>{t.label}</span>
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
        })}
      </div>
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
    overflowX: 'auto',
  },
  track: {
    display: 'flex',
    gap: '6px',
    alignItems: 'center',
    minWidth: 'max-content',
  },
  item: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 12px',
    borderRight: '1px solid var(--border)',
    whiteSpace: 'nowrap',
  },
  label: {
    fontSize: '11px',
    fontWeight: 600,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.3px',
  },
  price: {
    fontSize: '13px',
    fontWeight: 700,
  },
  change: {
    fontSize: '10px',
    fontWeight: 600,
    padding: '2px 6px',
    borderRadius: '4px',
  },
};
