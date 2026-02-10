import axios from 'axios';

const API_BASE = '/api';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 60000,  // 60s — handles cold-start scenarios
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

export async function lookupStockName(symbol, exchange = 'NSE') {
  const { data } = await api.get(`/stock/lookup/${encodeURIComponent(symbol)}`, { params: { exchange } });
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

// ── Contract Note Import ─────────────────────────────

function _readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      const b64 = result.split(',')[1];
      resolve(b64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export async function parseContractNote(file) {
  const base64 = await _readFileAsBase64(file);
  const payload = { pdf_base64: base64, filename: file.name };
  const { data } = await api.post('/portfolio/parse-contract-note', payload, { timeout: 120000 });
  // Attach the payload so we can reuse it for the confirm step
  data._payload = payload;
  return data;
}

export async function confirmImportContractNote(payload) {
  const { data } = await api.post('/portfolio/import-contract-note-confirmed', payload, { timeout: 120000 });
  return data;
}

// ── Market Ticker ────────────────────────────────────

export async function getMarketTicker() {
  const { data } = await api.get('/market-ticker');
  return data;
}

// ── Live Refresh (actual external fetch) ────────────

export async function triggerPriceRefresh() {
  // Longer timeout: refresh is synchronous — waits for Zerodha to respond
  const { data } = await api.post('/prices/refresh', null, { timeout: 120000 });
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
