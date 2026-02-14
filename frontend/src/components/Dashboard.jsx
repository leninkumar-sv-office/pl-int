import React from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function Dashboard({ summary, mfDashboard, loading }) {
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

  // Combine stock + MF numbers when MF data is available
  const hasMF = mfDashboard && mfDashboard.total_invested > 0;
  const totalInvested = summary.total_invested + (hasMF ? mfDashboard.total_invested : 0);
  const totalCurrentValue = summary.current_value + (hasMF ? mfDashboard.current_value : 0);
  const totalUnrealizedPL = summary.unrealized_pl + (hasMF ? mfDashboard.unrealized_pl : 0);
  const totalUnrealizedPLPct = totalInvested > 0 ? (totalUnrealizedPL / totalInvested) * 100 : 0;
  const totalRealizedPL = summary.realized_pl + (hasMF ? mfDashboard.realized_pl : 0);
  const totalHoldings = summary.total_holdings + (hasMF ? mfDashboard.total_funds : 0);
  const inProfit = summary.stocks_in_profit + (hasMF ? mfDashboard.funds_in_profit : 0);
  const inLoss = summary.stocks_in_loss + (hasMF ? mfDashboard.funds_in_loss : 0);

  const holdingSub = hasMF
    ? `${summary.total_holdings} stocks, ${mfDashboard.total_funds} funds`
    : `${summary.total_holdings} stocks`;

  const cards = [
    {
      label: 'Total Invested',
      value: formatINR(totalInvested),
      sub: holdingSub,
      color: 'var(--text)',
    },
    {
      label: 'Current Value',
      value: formatINR(totalCurrentValue),
      sub: totalCurrentValue >= totalInvested ? 'Above cost' : 'Below cost',
      color: totalCurrentValue >= totalInvested ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Unrealized P&L',
      value: formatINR(totalUnrealizedPL),
      sub: `${totalUnrealizedPLPct >= 0 ? '+' : ''}${totalUnrealizedPLPct.toFixed(2)}%`,
      color: totalUnrealizedPL >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Realized P&L',
      value: formatINR(totalRealizedPL),
      sub: totalRealizedPL >= 0 ? 'Net profit from sales' : 'Net loss from sales',
      color: totalRealizedPL >= 0 ? 'var(--green)' : 'var(--red)',
    },
    {
      label: 'Profit / Loss Split',
      value: `${inProfit} / ${inLoss}`,
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
