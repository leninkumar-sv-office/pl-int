import React from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function Dashboard({ summary, loading }) {
  if (loading && !summary) {
    return (
      <div className="summary-grid">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="summary-card">
            <div className="label">Loading...</div>
            <div className="value" style={{ color: 'var(--text-muted)' }}>--</div>
          </div>
        ))}
      </div>
    );
  }

  if (!summary) return null;

  const cards = [
    {
      label: 'Total Invested',
      value: formatINR(summary.total_invested),
      sub: `${summary.total_holdings} stocks`,
      color: 'var(--text)',
    },
    {
      label: 'Current Value',
      value: formatINR(summary.current_value),
      sub: summary.current_value >= summary.total_invested ? 'Above cost' : 'Below cost',
      color: summary.current_value >= summary.total_invested ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Unrealized P&L',
      value: formatINR(summary.unrealized_pl),
      sub: `${summary.unrealized_pl_pct >= 0 ? '+' : ''}${summary.unrealized_pl_pct.toFixed(2)}%`,
      color: summary.unrealized_pl >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Realized P&L',
      value: formatINR(summary.realized_pl),
      sub: summary.realized_pl >= 0 ? 'Net profit from sales' : 'Net loss from sales',
      color: summary.realized_pl >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Profit / Loss Split',
      value: `${summary.stocks_in_profit} / ${summary.stocks_in_loss}`,
      sub: 'In profit / In loss',
      color: 'var(--text)',
    },
    {
      label: 'Total Dividends',
      value: formatINR(summary.total_dividend || 0),
      sub: (summary.total_dividend || 0) > 0 ? 'Dividend income earned' : 'No dividends yet',
      color: (summary.total_dividend || 0) > 0 ? 'var(--green)' : 'var(--text-muted)',
    },
  ];

  return (
    <div className="summary-grid">
      {cards.map((card, i) => (
        <div key={i} className="summary-card">
          <div className="label">{card.label}</div>
          <div className="value" style={{ color: card.color }}>{card.value}</div>
          <div className={`sub ${card.color === 'var(--green)' ? 'positive' : card.color === 'var(--red)' ? 'negative' : 'neutral'}`}>
            {card.sub}
          </div>
        </div>
      ))}
    </div>
  );
}
