import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// ── Portfolio ─────────────────────────────────────────

export async function getPortfolio() {
  const { data } = await api.get('/portfolio');
  return data;
}

export async function addStock(stockData) {
  const { data } = await api.post('/portfolio/add', stockData);
  return data;
}

export async function sellStock(sellData) {
  const { data } = await api.post('/portfolio/sell', sellData);
  return data;
}

export async function deleteHolding(holdingId) {
  const { data } = await api.delete(`/portfolio/${holdingId}`);
  return data;
}

export async function getStockSummary() {
  const { data } = await api.get('/portfolio/stock-summary');
  return data;
}

// ── Transactions ──────────────────────────────────────

export async function getTransactions() {
  const { data } = await api.get('/transactions');
  return data;
}

// ── Dashboard ─────────────────────────────────────────

export async function getDashboardSummary() {
  const { data } = await api.get('/dashboard/summary');
  return data;
}

// ── Stock Data ────────────────────────────────────────

export async function getStockLive(symbol, exchange = 'NSE') {
  const { data } = await api.get(`/stock/${symbol}`, { params: { exchange } });
  return data;
}

export async function searchStock(query, exchange = 'NSE') {
  const { data } = await api.get(`/stock/search/${query}`, { params: { exchange } });
  return data;
}

export async function setManualPrice(symbol, exchange, price) {
  const { data } = await api.post('/stock/manual-price', { symbol, exchange, price });
  return data;
}

// ── Dividend ─────────────────────────────────────────

export async function addDividend(dividendData) {
  const { data } = await api.post('/portfolio/dividend', dividendData);
  return data;
}

// ── Market Ticker ────────────────────────────────────

export async function getMarketTicker() {
  const { data } = await api.get('/market-ticker');
  return data;
}

// ── Live Refresh (actual external fetch) ────────────

export async function triggerPriceRefresh() {
  const { data } = await api.post('/prices/refresh');
  return data;
}

export async function triggerTickerRefresh() {
  const { data } = await api.post('/market-ticker/refresh');
  return data;
}

// ── Settings ────────────────────────────────────────

export async function getRefreshInterval() {
  const { data } = await api.get('/settings/refresh-interval');
  return data;
}

export async function setRefreshInterval(interval) {
  const { data } = await api.post('/settings/refresh-interval', { interval });
  return data;
}

// ── Zerodha ────────────────────────────────────────

export async function getZerodhaStatus() {
  const { data } = await api.get('/zerodha/status');
  return data;
}

export async function getZerodhaLoginUrl() {
  const { data } = await api.get('/zerodha/login-url');
  return data;
}

export async function setZerodhaToken(accessToken) {
  const { data } = await api.post('/zerodha/set-token', { access_token: accessToken });
  return data;
}

export async function validateZerodha() {
  const { data } = await api.get('/zerodha/validate');
  return data;
}
