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

// ── Market Ticker ────────────────────────────────────

export async function getMarketTicker() {
  const { data } = await api.get('/market-ticker');
  return data;
}
