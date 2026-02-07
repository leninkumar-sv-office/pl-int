import React, { useState } from 'react';

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
        <div className="range-marker buy" style={{ left: `${buyPos}%` }} title={`Avg Buy: ${formatINR(buyPrice)}`} />
        <div className="range-marker current" style={{ left: `${currentPos}%` }} title={`Current: ${formatINR(current)}`} />
      </div>
      <div className="range-labels">
        <span>{formatINR(low)}</span>
        <span>{formatINR(high)}</span>
      </div>
    </div>
  );
}

export default function StockSummaryTable({ stocks, loading, onAddStock }) {
  const [sortField, setSortField] = useState('unrealized_pl');
  const [sortDir, setSortDir] = useState('desc');

  if (loading && stocks.length === 0) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading stock summary...
      </div>
    );
  }

  if (stocks.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📊</div>
        <h3>No stocks in your portfolio</h3>
        <p>Add your first stock to start tracking your investments.</p>
        <button className="btn btn-primary" onClick={onAddStock}>+ Add Your First Stock</button>
      </div>
    );
  }

  const handleSort = (field) => {
    if (sortField === field) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sorted = [...stocks].sort((a, b) => {
    let aVal, bVal;
    switch (sortField) {
      case 'symbol': aVal = a.symbol; bVal = b.symbol; break;
      case 'total_held_qty': aVal = a.total_held_qty; bVal = b.total_held_qty; break;
      case 'total_sold_qty': aVal = a.total_sold_qty; bVal = b.total_sold_qty; break;
      case 'total_invested': aVal = a.total_invested; bVal = b.total_invested; break;
      case 'current_value': aVal = a.current_value; bVal = b.current_value; break;
      case 'unrealized_profit': aVal = a.unrealized_profit; bVal = b.unrealized_profit; break;
      case 'unrealized_loss': aVal = a.unrealized_loss; bVal = b.unrealized_loss; break;
      case 'unrealized_pl': aVal = a.unrealized_pl; bVal = b.unrealized_pl; break;
      case 'realized_pl': aVal = a.realized_pl; bVal = b.realized_pl; break;
      default: aVal = a.unrealized_profit; bVal = b.unrealized_profit;
    }
    if (typeof aVal === 'string') {
      return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
  });

  const stocksWithHeld = stocks.filter(s => s.total_held_qty > 0);
  const totalHeldStocks = stocksWithHeld.length;
  const inProfit = stocksWithHeld.filter(s => s.is_above_avg_buy).length;
  const inLoss = stocksWithHeld.filter(s => !s.is_above_avg_buy && s.live).length;

  const SortIcon = ({ field }) => {
    if (sortField !== field) return <span style={{ opacity: 0.3, fontSize: '10px' }}> ↕</span>;
    return <span style={{ fontSize: '10px' }}> {sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Stock Summary</div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span className="section-badge">
            {totalHeldStocks} stocks held
          </span>
          <span className="section-badge" style={{ background: 'var(--green-bg)', color: 'var(--green)' }}>
            {inProfit} in profit
          </span>
          <span className="section-badge" style={{ background: 'var(--red-bg)', color: 'var(--red)' }}>
            {inLoss} in loss
          </span>
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer' }}>
                Stock<SortIcon field="symbol" />
              </th>
              <th onClick={() => handleSort('total_held_qty')} style={{ cursor: 'pointer' }}>
                Held<SortIcon field="total_held_qty" />
              </th>
              <th onClick={() => handleSort('total_sold_qty')} style={{ cursor: 'pointer' }}>
                Sold<SortIcon field="total_sold_qty" />
              </th>
              <th>Avg Buy</th>
              <th>Current Price</th>
              <th>52-Week Range</th>
              <th onClick={() => handleSort('total_invested')} style={{ cursor: 'pointer' }}>
                Invested<SortIcon field="total_invested" />
              </th>
              <th onClick={() => handleSort('current_value')} style={{ cursor: 'pointer' }}>
                Current Value<SortIcon field="current_value" />
              </th>
              <th onClick={() => handleSort('unrealized_profit')} style={{ cursor: 'pointer' }}>
                Unrealized PF<SortIcon field="unrealized_profit" />
              </th>
              <th onClick={() => handleSort('unrealized_loss')} style={{ cursor: 'pointer' }}>
                Unrealized Loss<SortIcon field="unrealized_loss" />
              </th>
              <th onClick={() => handleSort('realized_pl')} style={{ cursor: 'pointer' }}>
                Realized P&L<SortIcon field="realized_pl" />
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((stock) => {
              const live = stock.live;
              const currentPrice = live?.current_price || 0;
              const hasHeld = stock.total_held_qty > 0;

              return (
                <tr
                  key={stock.symbol}
                  className={stock.is_above_avg_buy && hasHeld ? 'highlight-profit' : ''}
                  style={{ opacity: hasHeld ? 1 : 0.6 }}
                >
                  <td>
                    <div className="stock-symbol">
                      {stock.symbol}
                      <span className="stock-exchange">{stock.exchange}</span>
                      {live?.is_manual && <span className="manual-badge">Manual</span>}
                    </div>
                    <div className="stock-name">{stock.name}</div>
                  </td>
                  <td>
                    <div style={{ fontWeight: 700, fontSize: '15px' }}>
                      {stock.total_held_qty > 0 ? stock.total_held_qty : '-'}
                    </div>
                    {stock.num_held_lots > 1 && (
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {stock.num_held_lots} lots
                      </div>
                    )}
                  </td>
                  <td>
                    {stock.total_sold_qty > 0 ? (
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--yellow)' }}>
                          {stock.total_sold_qty}
                        </div>
                        {stock.num_sold_lots > 1 && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                            {stock.num_sold_lots} trades
                          </div>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>-</span>
                    )}
                  </td>
                  <td>{hasHeld ? formatINR(stock.avg_buy_price) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td>
                    {live ? (
                      <div>
                        <div style={{
                          fontWeight: 600,
                          color: hasHeld
                            ? (currentPrice >= stock.avg_buy_price ? 'var(--green)' : 'var(--red)')
                            : 'var(--text)',
                        }}>
                          {formatINR(currentPrice)}
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
                        current={currentPrice}
                        buyPrice={stock.avg_buy_price}
                      />
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>N/A</span>
                    )}
                  </td>
                  <td>{hasHeld ? formatINR(stock.total_invested) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                  <td style={{ fontWeight: 600 }}>
                    {hasHeld ? formatINR(stock.current_value) : <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>-</span>}
                  </td>
                  <td>
                    {hasHeld && stock.unrealized_profit > 0 ? (
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--green)' }}>
                          +{formatINR(stock.unrealized_profit)}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          on {stock.profitable_qty} units
                        </div>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>-</span>
                    )}
                  </td>
                  <td>
                    {hasHeld && stock.unrealized_loss < 0 ? (
                      <div>
                        <div style={{ fontWeight: 600, color: 'var(--red)' }}>
                          {formatINR(stock.unrealized_loss)}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          on {stock.loss_qty} units
                        </div>
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>-</span>
                    )}
                  </td>
                  <td>
                    {stock.realized_pl !== 0 ? (
                      <div style={{
                        fontWeight: 600,
                        color: stock.realized_pl >= 0 ? 'var(--green)' : 'var(--red)',
                      }}>
                        {stock.realized_pl >= 0 ? '+' : ''}{formatINR(stock.realized_pl)}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>-</span>
                    )}
                  </td>
                  <td>
                    {hasHeld && stock.profitable_qty > 0 ? (
                      <div>
                        <div className="sell-tag">
                          ▲ Can Sell {stock.profitable_qty}
                        </div>
                        {stock.loss_qty > 0 && (
                          <div style={{
                            fontSize: '11px',
                            color: 'var(--red)',
                            marginTop: '4px',
                          }}>
                            {stock.loss_qty} in loss
                          </div>
                        )}
                      </div>
                    ) : hasHeld ? (
                      <div>
                        <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Hold</span>
                        <div style={{
                          fontSize: '11px',
                          color: 'var(--red)',
                          marginTop: '2px',
                        }}>
                          {stock.loss_qty} in loss
                        </div>
                      </div>
                    ) : (
                      <span style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        background: 'var(--bg-input)',
                        padding: '2px 8px',
                        borderRadius: '10px',
                      }}>
                        Fully Sold
                      </span>
                    )}
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
