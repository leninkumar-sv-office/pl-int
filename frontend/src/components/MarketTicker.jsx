import React, { useState, useCallback, useEffect } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { getTickerHistory } from '../services/api';

function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= breakpoint);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth <= breakpoint);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [breakpoint]);
  return isMobile;
}

const CHART_PERIODS = ['1D', '5D', '1M', '6M', 'YTD', '1Y', '5Y', 'MAX'];

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

const fmtTickerAmt = (v, type) => {
  if (!v || Math.abs(v) < 0.01) return '';
  const abs = Math.abs(v);
  const sign = v >= 0 ? '+' : '-';
  const prefix = type === 'index' ? '' : '₹';
  if (abs >= 10000000) return `${sign}${prefix}${(abs / 10000000).toFixed(1)}Cr`;
  if (abs >= 100000) return `${sign}${prefix}${(abs / 100000).toFixed(1)}L`;
  if (abs >= 1000) return `${sign}${prefix}${(abs / 1000).toFixed(1)}K`;
  if (abs >= 1) return `${sign}${prefix}${abs.toFixed(abs >= 100 ? 0 : 1)}`;
  return `${sign}${prefix}${abs.toFixed(2)}`;
};

const formatChartDate = (dateStr, period) => {
  const d = new Date(dateStr);
  if (period === '1d' || period === '5d') return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
  if (period === '1m') return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  return d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' });
};

const ChangeLine = ({ label, pct, amt }) => {
  if (!pct || pct === 0) return null;
  return (
    <span style={{ fontSize: '10px', color: pct >= 0 ? 'var(--green)' : 'var(--red)' }}>
      {label}: {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%{amt ? `, ${amt}` : ''}
    </span>
  );
};

export default function MarketTicker({ tickers, loading, lastUpdated }) {
  const isMobile = useIsMobile();
  const [expandedKey, setExpandedKey] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [chartPeriod, setChartPeriod] = useState('1y');
  const [chartLoading, setChartLoading] = useState(false);

  const fetchChart = useCallback(async (key, period) => {
    setChartLoading(true);
    setChartData([]);
    try {
      const data = await getTickerHistory(key, period);
      setChartData(Array.isArray(data) ? data : []);
    } catch {
      setChartData([]);
    }
    setChartLoading(false);
  }, []);

  const handleTickerClick = useCallback((key, hasToken) => {
    if (!hasToken) return;
    if (expandedKey === key) {
      setExpandedKey(null);
    } else {
      setExpandedKey(key);
      setChartPeriod('1y');
      fetchChart(key, '1y');
    }
  }, [expandedKey, fetchChart]);

  const handlePeriodChange = useCallback((period, key) => {
    const p = period.toLowerCase();
    setChartPeriod(p);
    fetchChart(key, p);
  }, [fetchChart]);

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
  const INDEX_KEYS = new Set(['SENSEX', 'NIFTY50', 'GIFTNIFTY', 'SGX', 'NIKKEI', 'SGDINR', 'USDINR']);
  const row1 = tickers.filter((t) => INDEX_KEYS.has(t.key));
  const row2 = tickers.filter((t) => !INDEX_KEYS.has(t.key));
  const cols = Math.max(row1.length, row2.length);

  const chartUp = chartData.length >= 2 && chartData[chartData.length - 1].close >= chartData[0].close;
  const chartColor = chartUp ? '#00d26a' : '#ff4757';

  const renderItem = (t, idx, rowLen) => {
    const hasData = t.price > 0;
    const isLast = idx === rowLen - 1;
    const d = t.change_pct || 0;
    const w = t.week_change_pct || 0;
    const m = t.month_change_pct || 0;
    const dAmt = t.change ? fmtTickerAmt(t.change, t.type) : '';
    const wAmt = w ? fmtTickerAmt(t.price * w / (100 + w), t.type) : '';
    const mAmt = m ? fmtTickerAmt(t.price * m / (100 + m), t.type) : '';
    const priceColor = d >= 0 ? 'var(--green)' : 'var(--red)';
    const hasToken = !!t.instrument_token;
    const isExpanded = expandedKey === t.key;
    return (
      <div key={t.key} style={{
        ...(isMobile ? styles.itemMobile : styles.item),
        borderRight: isMobile ? 'none' : (isLast ? 'none' : '1px solid var(--border)'),
        borderBottom: isMobile ? '1px solid var(--border)' : 'none',
        cursor: hasToken ? 'pointer' : 'default',
        background: isExpanded ? 'rgba(255,255,255,0.03)' : 'transparent',
        borderRadius: isExpanded ? '4px' : 0,
      }}
        onClick={() => handleTickerClick(t.key, hasToken)}
      >
        <span style={isMobile ? styles.labelMobile : styles.label}>{t.label}{t.unit ? <span style={{ fontWeight: 400, opacity: 0.6, fontSize: '10px', marginLeft: '2px' }}>{t.unit.replace('₹', '')}</span> : null}</span>
        {hasData ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: isMobile ? 4 : 6, flexWrap: 'wrap' }}>
              <span style={{ ...(isMobile ? styles.priceMobile : styles.price), color: priceColor }}>
                {formatPrice(t.price, t.type)}
              </span>
              {d !== 0 && (
                <span style={{
                  fontSize: isMobile ? '10px' : '11px',
                  fontWeight: 600,
                  color: d >= 0 ? 'var(--green)' : 'var(--red)',
                  background: d >= 0 ? 'rgba(0,210,106,0.12)' : 'rgba(255,71,87,0.12)',
                  padding: '1px 5px',
                  borderRadius: '3px',
                }}>
                  {d >= 0 ? '▲' : '▼'} {Math.abs(d).toFixed(2)}%{dAmt ? `, ${dAmt}` : ''}
                </span>
              )}
            </div>
            {!isMobile && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              <span style={{ fontSize: '10px', color: d >= 0 ? 'var(--green)' : 'var(--red)' }}>
                1D: {d >= 0 ? '+' : ''}{d.toFixed(2)}%, {dAmt || '+0'}
              </span>
              <ChangeLine label="7D" pct={w} amt={wAmt} />
              <ChangeLine label="1M" pct={m} amt={mAmt} />
            </div>
            )}
          </div>
        ) : (
          <span style={{ ...styles.price, color: 'var(--text-muted)' }}>--</span>
        )}
      </div>
    );
  };

  const renderChart = () => {
    if (!expandedKey) return null;
    return (
      <div style={{
        borderTop: '1px solid var(--border)',
        padding: '12px 16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
        background: 'var(--surface, var(--bg-card))',
      }}>
        {/* Period tabs */}
        <div style={{ display: 'flex', gap: '2px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)', marginRight: '8px' }}>
            {tickers.find(t => t.key === expandedKey)?.label || expandedKey}
          </span>
          {CHART_PERIODS.map(p => (
            <button key={p} onClick={(e) => { e.stopPropagation(); handlePeriodChange(p, expandedKey); }}
              style={{
                padding: '3px 8px', fontSize: '11px', fontWeight: 600, border: 'none', borderRadius: '4px', cursor: 'pointer',
                background: chartPeriod === p.toLowerCase() ? 'var(--text)' : 'transparent',
                color: chartPeriod === p.toLowerCase() ? 'var(--bg)' : 'var(--text-muted)',
              }}>
              {p}
            </button>
          ))}
        </div>
        {/* Chart area */}
        <div style={{ height: '200px' }}>
          {chartLoading ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>Loading chart...</div>
          ) : chartData.length === 0 ? (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '12px' }}>No data available</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id={`ticker-grad-${expandedKey}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={chartColor} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={chartColor} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fontSize: 12, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => formatChartDate(v, chartPeriod)}
                  interval="preserveStartEnd" minTickGap={50} />
                <YAxis domain={['auto', 'auto']} tick={{ fontSize: 12, fill: 'var(--text-muted)' }} tickLine={false} axisLine={false}
                  tickFormatter={(v) => v >= 100000 ? `${(v / 1000).toFixed(0)}k` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(v < 10 ? 2 : 0)} width={50} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: '6px', fontSize: '13px' }}
                  labelFormatter={(v) => {
                    const dt = new Date(v);
                    return (chartPeriod === '1d' || chartPeriod === '5d')
                      ? dt.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
                      : dt.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
                  }}
                  formatter={(value) => [value.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }), 'Close']}
                />
                <Area type="monotone" dataKey="close" stroke={chartColor} strokeWidth={1.5} fill={`url(#ticker-grad-${expandedKey})`} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    );
  };

  const fmtTime = lastUpdated ? new Date(lastUpdated).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : null;

  const gridCols = isMobile ? 2 : cols;

  return (
    <div style={styles.bar}>
      <div className="market-ticker-grid" style={{ display: 'grid', gridTemplateColumns: `repeat(${gridCols}, 1fr)` }}>
        {row1.map((t, i) => renderItem(t, i, row1.length))}
      </div>
      {row2.length > 0 && (
        <div className="market-ticker-grid" style={{ display: 'grid', gridTemplateColumns: `repeat(${gridCols}, 1fr)`, borderTop: '1px solid var(--border)' }}>
          {row2.map((t, i) => renderItem(t, i, row2.length))}
        </div>
      )}
      {renderChart()}
      {fmtTime && (
        <div style={{ textAlign: 'right', fontSize: '13px', color: 'var(--text-dim)', padding: '6px 12px 2px', fontWeight: 500 }}>
          Last updated: {fmtTime}
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
  itemMobile: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    gap: '2px',
    padding: '8px 10px',
  },
  label: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.3px',
  },
  labelMobile: {
    fontSize: '10px',
    fontWeight: 600,
    color: 'var(--text-dim)',
    textTransform: 'uppercase',
    letterSpacing: '0.3px',
  },
  price: {
    fontSize: '14px',
    fontWeight: 700,
  },
  priceMobile: {
    fontSize: '13px',
    fontWeight: 700,
  },
};
