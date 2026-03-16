export const mockPortfolio = {
  holdings: [
    { id: 'h1', symbol: 'RELIANCE', company: 'Reliance Industries', exchange: 'NSE', quantity: 10, buy_price: 2500, current_price: 2800, buy_date: '2024-01-15', gain: 3000, gain_pct: 12.0 },
    { id: 'h2', symbol: 'TCS', company: 'Tata Consultancy Services', exchange: 'NSE', quantity: 5, buy_price: 3400, current_price: 3600, buy_date: '2024-03-01', gain: 1000, gain_pct: 5.88 },
  ],
  summary: { total_invested: 42000, current_value: 47000, total_gain: 5000 },
};

export const mockMFSummary = {
  funds: [{ fund_code: 'INF846K01EW2', fund_name: 'Axis Bluechip Direct Growth', units: 100.5, avg_nav: 45.0, current_nav: 52.0, invested: 4522.5, current_value: 5226.0 }],
  total_invested: 4522.5, total_current: 5226.0,
};

export const mockMarketTicker = [
  { key: 'SENSEX', label: 'Sensex', price: 75000, change: 500, change_pct: 0.67, type: 'index' },
  { key: 'NIFTY', label: 'Nifty 50', price: 23000, change: -150, change_pct: -0.66, type: 'index' },
];

export const mockUsers = [
  { id: 'Lenin', name: 'Lenin', avatar: '\u{1F464}', color: '#4fc3f7', email: 'test@example.com' },
  { id: 'Appa', name: 'Appa', avatar: '\u{1F468}', color: '#81c784', email: 'test@example.com' },
];

export const mockDashboardSummary = {
  total_invested: 500000, current_value: 580000, total_gain: 80000, total_gain_pct: 16.0, stocks_count: 15, mf_count: 8,
};

export const mockFDDashboard = {
  deposits: [{ id: 'fd1', bank: 'SBI', principal: 100000, rate: 7.5, tenure_months: 12, start_date: '2024-01-01', maturity_date: '2025-01-01', status: 'Active', interest_payout: 'Cumulative' }],
};
