import React from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

function WeekRangeBar({ low, high, current, buyPrice }) {
  if (!low || !high || low >= high) {
    return <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>;
  }

  const range = high - low;
  const currentPos = Math.max(0, Math.min(100, ((current - low) / range) * 100));
  const buyPos = Math.max(0, Math.min(100, ((buyPrice - low) / range) * 100));

  return (
    <div className="range-bar-container">
      <div className="range-bar">
        <div className="range-bar-fill" style={{ width: '100%' }} />
        <div className="range-marker buy" style={{ left: `${buyPos}%` }} title={`Buy: ${formatINR(buyPrice)}`} />
        <div className="range-marker current" style={{ left: `${currentPos}%` }} title={`Current: ${formatINR(current)}`} />
      </div>
      <div className="range-labels">
        <span>{formatINR(low)}</span>
        <span>{formatINR(high)}</span>
      </div>
      <div className="range-legend">
        <span className="curr">CMP</span>
        <span className="buy">Buy</span>
      </div>
    </div>
  );
}

export default function PortfolioTable({ portfolio, loading, onSell, onAddStock }) {
  if (loading && portfolio.length === 0) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading portfolio...
      </div>
    );
  }

  if (portfolio.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📊</div>
        <h3>No stocks in your portfolio</h3>
        <p>Add your first stock to start tracking your investments.</p>
        <button className="btn btn-primary" onClick={onAddStock}>+ Add Your First Stock</button>
      </div>
    );
  }

  // Sort: stocks in profit (above buy price) first
  const sorted = [...portfolio].sort((a, b) => {
    if (a.is_above_buy_price && !b.is_above_buy_price) return -1;
    if (!a.is_above_buy_price && b.is_above_buy_price) return 1;
    return Math.abs(b.unrealized_pl) - Math.abs(a.unrealized_pl);
  });

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Your Holdings</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">
            {portfolio.filter(p => p.is_above_buy_price).length} in profit
          </span>
          <span className="section-badge" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
            {portfolio.filter(p => !p.is_above_buy_price && p.live).length} in loss
          </span>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th>Qty</th>
              <th>Buy Price</th>
              <th>Current Price</th>
              <th>52-Week Range</th>
              <th>Invested</th>
              <th>Current Value</th>
              <th>P&L</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((item) => {
              const h = item.holding;
              const live = item.live;
              const invested = h.buy_price * h.quantity;

              return (
                <tr key={h.id} className={item.is_above_buy_price ? 'highlight-profit' : ''}>
                  <td>
                    <div className="stock-symbol">
                      {h.symbol}
                      <span className="stock-exchange">{h.exchange}</span>
                      {live?.is_manual && <span className="manual-badge">Manual</span>}
                    </div>
                    <div className="stock-name">{h.name}</div>
                  </td>
                  <td style={{ fontWeight: 600 }}>{h.quantity}</td>
                  <td>{formatINR(h.buy_price)}</td>
                  <td>
                    {live ? (
                      <div>
                        <div style={{
                          fontWeight: 600,
                          color: live.current_price >= h.buy_price ? 'var(--green)' : 'var(--red)',
                        }}>
                          {formatINR(live.current_price)}
                        </div>
                        {live.day_change !== 0 && (
                          <div style={{
                            fontSize: '11px',
                            color: live.day_change >= 0 ? 'var(--green)' : 'var(--red)',
                          }}>
                            {live.day_change >= 0 ? '+' : ''}{live.day_change.toFixed(2)} ({live.day_change_pct.toFixed(2)}%)
                          </div>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>--</span>
                    )}
                  </td>
                  <td>
                    {live ? (
                      <WeekRangeBar
                        low={live.week_52_low}
                        high={live.week_52_high}
                        current={live.current_price}
                        buyPrice={h.buy_price}
                      />
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>
                    )}
                  </td>
                  <td>{formatINR(invested)}</td>
                  <td style={{ fontWeight: 600 }}>{formatINR(item.current_value)}</td>
                  <td>
                    <div style={{
                      fontWeight: 600,
                      color: item.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)',
                    }}>
                      {item.unrealized_pl >= 0 ? '+' : ''}{formatINR(item.unrealized_pl)}
                    </div>
                    <div style={{
                      fontSize: '11px',
                      color: item.unrealized_pl_pct >= 0 ? 'var(--green)' : 'var(--red)',
                    }}>
                      {item.unrealized_pl_pct >= 0 ? '+' : ''}{item.unrealized_pl_pct.toFixed(2)}%
                    </div>
                  </td>
                  <td>
                    {item.is_above_buy_price ? (
                      <div className="sell-tag">
                        ▲ Can Sell {h.quantity}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Hold</span>
                    )}
                  </td>
                  <td>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => onSell(item)}
                    >
                      Sell
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
