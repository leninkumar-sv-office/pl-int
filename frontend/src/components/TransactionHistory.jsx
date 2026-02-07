import React from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function TransactionHistory({ transactions }) {
  if (!transactions || transactions.length === 0) {
    return (
      <div className="empty-state">
        <div className="icon">📋</div>
        <h3>No transactions yet</h3>
        <p>Sold stocks will appear here with realized P&L.</p>
      </div>
    );
  }

  const totalRealized = transactions.reduce((sum, t) => sum + t.realized_pl, 0);
  const sorted = [...transactions].sort((a, b) => new Date(b.sell_date) - new Date(a.sell_date));

  return (
    <div className="section">
      <div className="section-header">
        <div className="section-title">Transaction History</div>
        <div className="section-badge" style={{
          background: totalRealized >= 0 ? 'var(--green-bg)' : 'var(--red-bg)',
          color: totalRealized >= 0 ? 'var(--green)' : 'var(--red)',
        }}>
          Total Realized: {totalRealized >= 0 ? '+' : ''}{formatINR(totalRealized)}
        </div>
      </div>

      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>Stock</th>
              <th>Qty Sold</th>
              <th>Buy Price</th>
              <th>Sell Price</th>
              <th>Buy Date</th>
              <th>Sell Date</th>
              <th>Invested</th>
              <th>Received</th>
              <th>Realized P&L</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((t) => {
              const invested = t.buy_price * t.quantity;
              const received = t.sell_price * t.quantity;
              return (
                <tr key={t.id}>
                  <td>
                    <div className="stock-symbol">
                      {t.symbol}
                      <span className="stock-exchange">{t.exchange}</span>
                    </div>
                    <div className="stock-name">{t.name}</div>
                  </td>
                  <td style={{ fontWeight: 600 }}>{t.quantity}</td>
                  <td>{formatINR(t.buy_price)}</td>
                  <td style={{
                    fontWeight: 600,
                    color: t.sell_price >= t.buy_price ? 'var(--green)' : 'var(--red)',
                  }}>
                    {formatINR(t.sell_price)}
                  </td>
                  <td style={{ color: 'var(--text-dim)' }}>{t.buy_date}</td>
                  <td style={{ color: 'var(--text-dim)' }}>{t.sell_date}</td>
                  <td>{formatINR(invested)}</td>
                  <td>{formatINR(received)}</td>
                  <td>
                    <div style={{
                      fontWeight: 700,
                      color: t.realized_pl >= 0 ? 'var(--green)' : 'var(--red)',
                    }}>
                      {t.realized_pl >= 0 ? '+' : ''}{formatINR(t.realized_pl)}
                    </div>
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
