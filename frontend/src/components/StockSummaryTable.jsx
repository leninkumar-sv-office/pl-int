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

/* ── Expanded detail panel inside a stock row ───────────── */
function StockDetail({ stock, portfolio, transactions, onSell, onAddStock, onDividend }) {
  const heldLots = (portfolio || []).filter(
    (item) => item.holding.symbol === stock.symbol && item.holding.quantity > 0
  );
  const soldTrades = (transactions || []).filter(
    (t) => t.symbol === stock.symbol
  );
  const live = stock.live;
  const cp = live?.current_price || 0;

  return (
    <div style={{
      background: 'var(--bg)',
      borderTop: '1px solid var(--border)',
      padding: '20px 24px',
    }}>
      {/* Action buttons — prominent at top */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginBottom: '20px',
        alignItems: 'center',
      }}>
        {heldLots.length > 0 && (
          <span style={{ fontSize: '13px', color: 'var(--text-dim)', marginRight: '4px' }}>
            Quick actions:
          </span>
        )}
        <button
          className="btn btn-primary"
          onClick={(e) => { e.stopPropagation(); onAddStock({ symbol: stock.symbol, exchange: stock.exchange, name: stock.name }); }}
          style={{ fontWeight: 600 }}
        >
          + Buy {stock.symbol}
        </button>
        <button
          className="btn btn-ghost"
          onClick={(e) => { e.stopPropagation(); onDividend({ symbol: stock.symbol, exchange: stock.exchange }); }}
          style={{ fontWeight: 600 }}
        >
          + Dividend
        </button>
      </div>

      {/* 52-week range + extra stats */}
      {live && (
        <div style={{
          display: 'flex',
          gap: '32px',
          marginBottom: '20px',
          padding: '14px 16px',
          background: 'var(--bg-card)',
          borderRadius: 'var(--radius-sm)',
          border: '1px solid var(--border)',
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>52-Week Range</div>
            <WeekRangeBar low={live.week_52_low} high={live.week_52_high} current={cp} buyPrice={stock.avg_buy_price} />
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Invested</div>
            <div style={{ fontWeight: 600 }}>{formatINR(stock.total_invested)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Current Value</div>
            <div style={{ fontWeight: 600 }}>{formatINR(stock.current_value)}</div>
          </div>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Unrealized P&L</div>
            <div style={{ fontWeight: 600, color: stock.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
              {stock.unrealized_pl >= 0 ? '+' : ''}{formatINR(stock.unrealized_pl)}
            </div>
          </div>
          {stock.realized_pl !== 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Realized P&L</div>
              <div style={{ fontWeight: 600, color: stock.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {stock.realized_pl >= 0 ? '+' : ''}{formatINR(stock.realized_pl)}
              </div>
            </div>
          )}
          {stock.total_dividend > 0 && (
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>Dividends</div>
              <div style={{ fontWeight: 600, color: 'var(--green)' }}>
                +{formatINR(stock.total_dividend)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Held Lots sub-table ────────────────────────── */}
      {heldLots.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)' }}>
            Held Lots ({heldLots.length})
          </div>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <th style={subTh}>Buy Date</th>
                  <th style={subTh}>Qty</th>
                  <th style={subTh}>Price</th>
                  <th style={subTh}>Buy Price</th>
                  <th style={subTh}>Total Cost</th>
                  <th style={subTh}>Current</th>
                  <th style={subTh}>P&L</th>
                  <th style={subTh}>Action</th>
                </tr>
              </thead>
              <tbody>
                {heldLots.map((item) => {
                  const h = item.holding;
                  const lotPL = cp > 0 ? (cp - h.buy_price) * h.quantity : 0;
                  const inProfit = cp > h.buy_price;
                  return (
                    <tr key={h.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={subTd}>{h.buy_date}</td>
                      <td style={{ ...subTd, fontWeight: 600 }}>{h.quantity}</td>
                      <td style={subTd}>{formatINR(h.price || h.buy_price)}</td>
                      <td style={subTd}>{formatINR(h.buy_price)}</td>
                      <td style={subTd}>{formatINR(h.buy_cost || (h.buy_price * h.quantity))}</td>
                      <td style={{ ...subTd, color: inProfit ? 'var(--green)' : 'var(--red)', fontWeight: 600 }}>
                        {cp > 0 ? formatINR(cp) : '--'}
                      </td>
                      <td style={{ ...subTd, fontWeight: 600, color: lotPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
                        {cp > 0 ? `${lotPL >= 0 ? '+' : ''}${formatINR(lotPL)}` : '--'}
                      </td>
                      <td style={subTd}>
                        <button
                          className={`btn btn-sm ${inProfit ? 'btn-success' : 'btn-danger'}`}
                          onClick={(e) => { e.stopPropagation(); onSell(item); }}
                          style={{ minWidth: '56px' }}
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
      )}

      {/* ── Sold Transactions sub-table ─────────────────── */}
      {soldTrades.length > 0 && (
        <div>
          <div style={{ fontSize: '14px', fontWeight: 600, marginBottom: '10px', color: 'var(--text)' }}>
            Sold Transactions ({soldTrades.length})
          </div>
          <div style={{
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                  <th style={subTh}>Buy Date</th>
                  <th style={subTh}>Sell Date</th>
                  <th style={subTh}>Qty</th>
                  <th style={subTh}>Buy Price</th>
                  <th style={subTh}>Sell Price</th>
                  <th style={subTh}>Realized P&L</th>
                </tr>
              </thead>
              <tbody>
                {soldTrades.map((t, idx) => (
                  <tr key={t.id || idx} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={subTd}>{t.buy_date}</td>
                    <td style={subTd}>{t.sell_date}</td>
                    <td style={{ ...subTd, fontWeight: 600 }}>{t.quantity}</td>
                    <td style={subTd}>{formatINR(t.buy_price)}</td>
                    <td style={subTd}>{formatINR(t.sell_price)}</td>
                    <td style={{ ...subTd, fontWeight: 600, color: t.realized_pl >= 0 ? 'var(--green)' : 'var(--red)' }}>
                      {t.realized_pl >= 0 ? '+' : ''}{formatINR(t.realized_pl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {heldLots.length === 0 && soldTrades.length === 0 && (
        <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px' }}>
          No lot or transaction details available.
        </div>
      )}
    </div>
  );
}

const subTh = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: '11px',
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  color: 'var(--text-dim)',
  fontWeight: 600,
  borderBottom: '1px solid var(--border)',
};

const subTd = {
  padding: '10px 14px',
  fontSize: '13px',
  verticalAlign: 'middle',
};


/* ── Main Table ───────────────────────────────────────── */
export default function StockSummaryTable({ stocks, loading, onAddStock, portfolio, onSell, onDividend, transactions }) {
  const [sortField, setSortField] = useState('unrealized_pl');
  const [sortDir, setSortDir] = useState('desc');
  const [expandedSymbol, setExpandedSymbol] = useState(null);

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
        <button className="btn btn-primary" onClick={() => onAddStock({})}>+ Add Your First Stock</button>
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

  const toggleExpand = (symbol) => {
    setExpandedSymbol(prev => prev === symbol ? null : symbol);
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
      case 'total_dividend': aVal = a.total_dividend || 0; bVal = b.total_dividend || 0; break;
      case 'week_52_low': {
        const aCP = a.live?.current_price || 0, aLow = a.live?.week_52_low || 0;
        const bCP = b.live?.current_price || 0, bLow = b.live?.week_52_low || 0;
        aVal = aLow > 0 && aCP > 0 ? ((aCP - aLow) / aLow * 100) : 9999;
        bVal = bLow > 0 && bCP > 0 ? ((bCP - bLow) / bLow * 100) : 9999;
        break;
      }
      case 'week_52_high': {
        const aCP2 = a.live?.current_price || 0, aHigh = a.live?.week_52_high || 0;
        const bCP2 = b.live?.current_price || 0, bHigh = b.live?.week_52_high || 0;
        aVal = aHigh > 0 && aCP2 > 0 ? ((aHigh - aCP2) / aHigh * 100) : 9999;
        bVal = bHigh > 0 && bCP2 > 0 ? ((bHigh - bCP2) / bHigh * 100) : 9999;
        break;
      }
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

  const TOTAL_COLS = 15; // number of columns in the main table

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

      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '12px' }}>
        Click any row to view lots, transactions, and Buy/Sell actions
      </div>

      <div className="table-container" style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th style={{ width: '28px' }}></th>
              <th onClick={() => handleSort('symbol')} style={{ cursor: 'pointer' }}>
                Stock<SortIcon field="symbol" />
              </th>
              <th onClick={() => handleSort('total_held_qty')} style={{ cursor: 'pointer' }}>
                Held<SortIcon field="total_held_qty" />
              </th>
              <th onClick={() => handleSort('total_sold_qty')} style={{ cursor: 'pointer' }}>
                Sold<SortIcon field="total_sold_qty" />
              </th>
              <th>Price</th>
              <th>Buy Price</th>
              <th>Total Cost</th>
              <th>Current Price</th>
              <th onClick={() => handleSort('week_52_low')} style={{ cursor: 'pointer' }}>
                52W Low<SortIcon field="week_52_low" />
              </th>
              <th onClick={() => handleSort('week_52_high')} style={{ cursor: 'pointer' }}>
                52W High<SortIcon field="week_52_high" />
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
              <th onClick={() => handleSort('total_dividend')} style={{ cursor: 'pointer' }}>
                Dividends<SortIcon field="total_dividend" />
              </th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((stock) => {
              const live = stock.live;
              const currentPrice = live?.current_price || 0;
              const hasHeld = stock.total_held_qty > 0;
              const isExpanded = expandedSymbol === stock.symbol;

              return (
                <React.Fragment key={stock.symbol}>
                  {/* ── Main summary row (clickable) ─────────── */}
                  <tr
                    className={stock.is_above_avg_buy && hasHeld ? 'highlight-profit' : ''}
                    style={{
                      opacity: hasHeld ? 1 : 0.6,
                      cursor: 'pointer',
                      background: isExpanded ? 'var(--bg-card-hover)' : undefined,
                    }}
                    onClick={() => toggleExpand(stock.symbol)}
                  >
                    {/* Expand indicator */}
                    <td style={{ padding: '14px 4px 14px 16px', width: '28px', fontSize: '14px', color: 'var(--text-dim)' }}>
                      {isExpanded ? '▾' : '▸'}
                    </td>
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
                    <td>{hasHeld ? formatINR(stock.avg_price) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                    <td>{hasHeld ? formatINR(stock.avg_buy_price) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
                    <td>{hasHeld ? formatINR(stock.total_invested) : <span style={{ color: 'var(--text-muted)' }}>-</span>}</td>
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
                      {live?.week_52_low ? (() => {
                        const nearLow = currentPrice > 0 && currentPrice <= live.week_52_low * 1.05;
                        const pctFromLow = currentPrice > 0 && live.week_52_low > 0
                          ? ((currentPrice - live.week_52_low) / live.week_52_low * 100) : 0;
                        return (
                          <div>
                            <div style={{
                              fontSize: '13px',
                              color: nearLow ? 'var(--red)' : 'var(--text)',
                              fontWeight: nearLow ? 600 : 400,
                            }}>
                              {formatINR(live.week_52_low)}
                            </div>
                            {currentPrice > 0 && (
                              <div style={{ fontSize: '11px', color: nearLow ? 'var(--red)' : 'var(--text)', fontWeight: nearLow ? 600 : 400 }}>
                                +{pctFromLow.toFixed(1)}% away
                              </div>
                            )}
                          </div>
                        );
                      })() : (
                        <span style={{ color: 'var(--text-muted)' }}>--</span>
                      )}
                    </td>
                    <td>
                      {live?.week_52_high ? (() => {
                        const nearHigh = currentPrice > 0 && currentPrice >= live.week_52_high * 0.95;
                        const pctFromHigh = currentPrice > 0 && live.week_52_high > 0
                          ? ((live.week_52_high - currentPrice) / live.week_52_high * 100) : 0;
                        return (
                          <div>
                            <div style={{
                              fontSize: '13px',
                              color: nearHigh ? 'var(--green)' : 'var(--text)',
                              fontWeight: nearHigh ? 600 : 400,
                            }}>
                              {formatINR(live.week_52_high)}
                            </div>
                            {currentPrice > 0 && (
                              <div style={{ fontSize: '11px', color: nearHigh ? 'var(--green)' : 'var(--text)', fontWeight: nearHigh ? 600 : 400 }}>
                                -{pctFromHigh.toFixed(1)}% away
                              </div>
                            )}
                          </div>
                        );
                      })() : (
                        <span style={{ color: 'var(--text-muted)' }}>--</span>
                      )}
                    </td>
                    <td>
                      {hasHeld && stock.unrealized_profit > 0 ? (
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--green)' }}>
                            +{formatINR(stock.unrealized_profit)}
                          </div>
                          <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85 }}>
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
                          <div style={{ fontSize: '11px', color: 'var(--red)', opacity: 0.85 }}>
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
                      {(stock.total_dividend || 0) > 0 ? (
                        <div>
                          <div style={{ fontWeight: 600, color: 'var(--green)' }}>
                            +{formatINR(stock.total_dividend)}
                          </div>
                          {(stock.dividend_units || 0) > 0 && (
                            <div style={{ fontSize: '11px', color: 'var(--green)', opacity: 0.85 }}>
                              on {stock.dividend_units} units
                            </div>
                          )}
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
                            <div style={{ fontSize: '11px', color: 'var(--red)', marginTop: '4px' }}>
                              {stock.loss_qty} in loss
                            </div>
                          )}
                        </div>
                      ) : hasHeld ? (
                        <div>
                          <span style={{ color: 'var(--text-dim)', fontSize: '12px' }}>Hold</span>
                          {stock.loss_qty > 0 && (
                            <div style={{ fontSize: '11px', color: 'var(--red)', marginTop: '2px' }}>
                              {stock.loss_qty} in loss
                            </div>
                          )}
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

                  {/* ── Expanded detail row ──────────────────── */}
                  {isExpanded && (
                    <tr>
                      <td colSpan={TOTAL_COLS} style={{ padding: 0 }}>
                        <StockDetail
                          stock={stock}
                          portfolio={portfolio}
                          transactions={transactions}
                          onSell={onSell}
                          onAddStock={onAddStock}
                          onDividend={onDividend}
                        />
                      </td>
                    </tr>
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
