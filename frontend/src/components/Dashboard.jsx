import React, { useState } from 'react';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function Dashboard({ summary, mfDashboard, fdDashboard, rdDashboard, ppfDashboard, npsDashboard, loading }) {
  const [expanded, setExpanded] = useState(() => localStorage.getItem('dashboardExpanded') === 'true');

  const toggle = () => {
    const next = !expanded;
    setExpanded(next);
    localStorage.setItem('dashboardExpanded', String(next));
  };

  if (loading && !summary) {
    return (
      <div className="dashboard-section">
        <button className="dashboard-toggle" onClick={toggle}>
          <span className={`toggle-arrow ${expanded ? 'expanded' : ''}`}>&#9656;</span>
          <span className="toggle-label">Portfolio Summary</span>
        </button>
        {expanded && (
          <div className="summary-grid">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="summary-card">
                <div className="label">Loading...</div>
                <div className="value" style={{ color: 'var(--text-muted)' }}>--</div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (!summary) return null;

  // ── Stocks ──
  const stockInvested = summary.total_invested || 0;
  const stockCurrent = summary.current_value || 0;
  const stockUnrealized = summary.unrealized_pl || 0;
  const stockRealized = summary.realized_pl || 0;

  // ── Mutual Funds ──
  const hasMF = mfDashboard && mfDashboard.total_invested > 0;
  const mfInvested = hasMF ? mfDashboard.total_invested : 0;
  const mfCurrent = hasMF ? mfDashboard.current_value : 0;
  const mfUnrealized = hasMF ? mfDashboard.unrealized_pl : 0;
  const mfRealized = hasMF ? mfDashboard.realized_pl : 0;

  // ── Fixed Deposits ──
  const hasFD = fdDashboard && fdDashboard.total_invested > 0;
  const fdInvested = hasFD ? fdDashboard.total_invested : 0;
  const fdCurrent = hasFD ? (fdDashboard.total_invested + (fdDashboard.total_interest || 0)) : 0;
  const fdGain = hasFD ? (fdDashboard.total_interest || 0) : 0;

  // ── Recurring Deposits ──
  const hasRD = rdDashboard && rdDashboard.total_deposited > 0;
  const rdInvested = hasRD ? rdDashboard.total_deposited : 0;
  const rdCurrent = hasRD ? (rdDashboard.total_deposited + (rdDashboard.total_interest_accrued || 0)) : 0;
  const rdGain = hasRD ? (rdDashboard.total_interest_accrued || 0) : 0;

  // ── PPF ──
  const hasPPF = ppfDashboard && ppfDashboard.net_invested > 0;
  const ppfInvested = hasPPF ? ppfDashboard.net_invested : 0;
  const ppfCurrent = hasPPF ? (ppfDashboard.current_balance || 0) : 0;
  const ppfGain = hasPPF ? (ppfDashboard.total_interest || 0) : 0;

  // ── NPS ──
  const hasNPS = npsDashboard && npsDashboard.total_contributed > 0;
  const npsInvested = hasNPS ? npsDashboard.total_contributed : 0;
  const npsCurrent = hasNPS ? npsDashboard.current_value : 0;
  const npsGain = hasNPS ? npsDashboard.total_gain : 0;

  // ── Totals ──
  const totalInvested = stockInvested + mfInvested + fdInvested + rdInvested + ppfInvested + npsInvested;
  const totalCurrentValue = stockCurrent + mfCurrent + fdCurrent + rdCurrent + ppfCurrent + npsCurrent;
  const totalUnrealizedPL = totalCurrentValue - totalInvested;
  const totalUnrealizedPLPct = totalInvested > 0 ? (totalUnrealizedPL / totalInvested) * 100 : 0;
  const totalRealizedPL = stockRealized + mfRealized;

  const inProfit = summary.stocks_in_profit + (hasMF ? mfDashboard.funds_in_profit : 0);
  const inLoss = summary.stocks_in_loss + (hasMF ? mfDashboard.funds_in_loss : 0);

  // Build holdings subtitle
  const parts = [];
  if (summary.total_holdings) parts.push(`${summary.total_holdings} stocks`);
  if (hasMF) parts.push(`${mfDashboard.total_funds} funds`);
  if (hasFD) parts.push(`${fdDashboard.active_count} FDs`);
  if (hasRD) parts.push(`${rdDashboard.active_count} RDs`);
  if (hasPPF) parts.push(`${ppfDashboard.active_count} PPF`);
  if (hasNPS) parts.push(`${npsDashboard.active_count} NPS`);
  const holdingSub = parts.join(', ');

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

  // Collapsed inline summary
  const collapsedSummary = `${formatINR(totalCurrentValue)}  ·  P&L ${totalUnrealizedPL >= 0 ? '+' : ''}${formatINR(totalUnrealizedPL)} (${totalUnrealizedPLPct >= 0 ? '+' : ''}${totalUnrealizedPLPct.toFixed(2)}%)`;

  return (
    <div className="dashboard-section">
      <button className="dashboard-toggle" onClick={toggle}>
        <span className={`toggle-arrow ${expanded ? 'expanded' : ''}`}>&#9656;</span>
        <span className="toggle-label">Portfolio Summary</span>
        {!expanded && (
          <span className="toggle-summary" style={{ color: totalUnrealizedPL >= 0 ? 'var(--green)' : 'var(--red)' }}>
            {collapsedSummary}
          </span>
        )}
      </button>
      {expanded && (
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
      )}
    </div>
  );
}
