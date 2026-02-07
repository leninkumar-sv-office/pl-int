import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell,
  ComposedChart, Line, Area,
  ReferenceLine,
} from 'recharts';

const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  const abs = Math.abs(num);
  if (abs >= 10000000) return '₹' + (num / 10000000).toFixed(2) + ' Cr';
  if (abs >= 100000) return '₹' + (num / 100000).toFixed(2) + ' L';
  if (abs >= 1000) return '₹' + (num / 1000).toFixed(1) + 'K';
  return '₹' + num.toFixed(0);
};

const COLORS = ['#4e7cff', '#00d26a', '#ff4757', '#ffc048', '#a855f7', '#06b6d4', '#f472b6', '#84cc16'];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: '8px',
      padding: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
    }}>
      <div style={{ fontWeight: 600, marginBottom: '8px', color: '#e4e6ed' }}>{label}</div>
      {payload.map((entry, i) => (
        <div key={i} style={{ color: entry.color, fontSize: '13px', marginBottom: '2px' }}>
          {entry.name}: {typeof entry.value === 'number'
            ? '₹' + entry.value.toLocaleString('en-IN', { minimumFractionDigits: 2 })
            : entry.value}
        </div>
      ))}
    </div>
  );
};

export default function Charts({ portfolio, summary, transactions }) {
  // ── P&L per stock (bar chart) ──────────────────────
  const plData = useMemo(() => {
    if (!portfolio?.length) return [];
    return portfolio
      .filter(p => p.live)
      .map(p => ({
        name: p.holding.symbol,
        'Unrealized P&L': p.unrealized_pl,
        invested: p.holding.buy_price * p.holding.quantity,
        current: p.current_value,
      }))
      .sort((a, b) => b['Unrealized P&L'] - a['Unrealized P&L']);
  }, [portfolio]);

  // ── Portfolio composition (pie chart) ──────────────
  const compositionData = useMemo(() => {
    if (!portfolio?.length) return [];
    return portfolio
      .filter(p => p.current_value > 0)
      .map(p => ({
        name: p.holding.symbol,
        value: p.current_value,
      }))
      .sort((a, b) => b.value - a.value);
  }, [portfolio]);

  // ── 52-Week range chart ────────────────────────────
  const rangeData = useMemo(() => {
    if (!portfolio?.length) return [];
    return portfolio
      .filter(p => p.live && p.live.week_52_low > 0 && p.live.week_52_high > 0)
      .map(p => ({
        name: p.holding.symbol,
        low: p.live.week_52_low,
        high: p.live.week_52_high,
        current: p.live.current_price,
        buy: p.holding.buy_price,
        range: p.live.week_52_high - p.live.week_52_low,
        // Position within range (0-100%)
        position: ((p.live.current_price - p.live.week_52_low) / (p.live.week_52_high - p.live.week_52_low) * 100).toFixed(1),
      }));
  }, [portfolio]);

  // ── Realized vs Unrealized (summary) ───────────────
  const plSummaryData = useMemo(() => {
    if (!summary) return [];
    return [
      { name: 'Unrealized P&L', value: summary.unrealized_pl, fill: summary.unrealized_pl >= 0 ? '#00d26a' : '#ff4757' },
      { name: 'Realized P&L', value: summary.realized_pl, fill: summary.realized_pl >= 0 ? '#4e7cff' : '#ff4757' },
    ];
  }, [summary]);

  if (!portfolio?.length) {
    return (
      <div className="empty-state">
        <div className="icon">📈</div>
        <h3>No data for charts</h3>
        <p>Add stocks to see visual analytics.</p>
      </div>
    );
  }

  return (
    <div>
      {/* Row 1: P&L Bar Chart + Portfolio Composition */}
      <div className="charts-grid">
        <div className="chart-card">
          <h3>Unrealized P&L by Stock</h3>
          {plData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={plData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                <XAxis dataKey="name" tick={{ fill: '#8b8fa3', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8b8fa3', fontSize: 12 }} tickFormatter={formatINR} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke="#5c6078" />
                <Bar dataKey="Unrealized P&L" radius={[4, 4, 0, 0]}>
                  {plData.map((entry, index) => (
                    <Cell
                      key={index}
                      fill={entry['Unrealized P&L'] >= 0 ? '#00d26a' : '#ff4757'}
                      fillOpacity={0.8}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>No live data</div>
          )}
        </div>

        <div className="chart-card">
          <h3>Portfolio Composition</h3>
          {compositionData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={compositionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={{ stroke: '#5c6078' }}
                >
                  {compositionData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>No data</div>
          )}
        </div>
      </div>

      {/* Row 2: 52-Week Range + Realized vs Unrealized */}
      <div className="charts-grid">
        <div className="chart-card">
          <h3>52-Week Position (% from Low)</h3>
          {rangeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={rangeData} layout="vertical" margin={{ top: 5, right: 30, bottom: 5, left: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#8b8fa3', fontSize: 12 }} tickFormatter={(v) => v + '%'} />
                <YAxis dataKey="name" type="category" tick={{ fill: '#8b8fa3', fontSize: 12 }} width={60} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d = payload[0]?.payload;
                    if (!d) return null;
                    return (
                      <div style={{
                        background: '#1a1d27', border: '1px solid #2a2d3a', borderRadius: '8px',
                        padding: '12px', boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
                      }}>
                        <div style={{ fontWeight: 600, marginBottom: '6px', color: '#e4e6ed' }}>{d.name}</div>
                        <div style={{ fontSize: '12px', color: '#8b8fa3' }}>52W Low: ₹{d.low?.toLocaleString('en-IN')}</div>
                        <div style={{ fontSize: '12px', color: '#8b8fa3' }}>52W High: ₹{d.high?.toLocaleString('en-IN')}</div>
                        <div style={{ fontSize: '12px', color: '#4e7cff' }}>Current: ₹{d.current?.toLocaleString('en-IN')}</div>
                        <div style={{ fontSize: '12px', color: '#ffc048' }}>Buy: ₹{d.buy?.toLocaleString('en-IN')}</div>
                        <div style={{ fontSize: '12px', color: '#e4e6ed', marginTop: '4px', fontWeight: 600 }}>
                          Position: {d.position}% from low
                        </div>
                      </div>
                    );
                  }}
                />
                <Bar dataKey="position" radius={[0, 4, 4, 0]} name="Position %">
                  {rangeData.map((entry, index) => {
                    const pos = parseFloat(entry.position);
                    let color = '#ff4757'; // Near low
                    if (pos > 66) color = '#00d26a'; // Near high
                    else if (pos > 33) color = '#ffc048'; // Mid range
                    return <Cell key={index} fill={color} fillOpacity={0.8} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>No 52-week data</div>
          )}
        </div>

        <div className="chart-card">
          <h3>Realized vs Unrealized P&L</h3>
          {plSummaryData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={plSummaryData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                <XAxis dataKey="name" tick={{ fill: '#8b8fa3', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8b8fa3', fontSize: 12 }} tickFormatter={formatINR} />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine y={0} stroke="#5c6078" />
                <Bar dataKey="value" name="P&L" radius={[4, 4, 0, 0]}>
                  {plSummaryData.map((entry, index) => (
                    <Cell key={index} fill={entry.fill} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>No P&L data</div>
          )}
        </div>
      </div>

      {/* Row 3: Invested vs Current Value */}
      <div className="charts-grid" style={{ gridTemplateColumns: '1fr' }}>
        <div className="chart-card">
          <h3>Invested vs Current Value per Stock</h3>
          {plData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <ComposedChart data={plData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2d3a" />
                <XAxis dataKey="name" tick={{ fill: '#8b8fa3', fontSize: 12 }} />
                <YAxis tick={{ fill: '#8b8fa3', fontSize: 12 }} tickFormatter={formatINR} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ color: '#8b8fa3' }} />
                <Bar dataKey="invested" name="Invested" fill="#4e7cff" fillOpacity={0.6} radius={[4, 4, 0, 0]} />
                <Bar dataKey="current" name="Current Value" fill="#00d26a" fillOpacity={0.6} radius={[4, 4, 0, 0]} />
              </ComposedChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>No data</div>
          )}
        </div>
      </div>
    </div>
  );
}
