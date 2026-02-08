import React, { useState, useEffect, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { getPortfolio, getDashboardSummary, getTransactions, addStock, sellStock, addDividend, getStockSummary, getMarketTicker, triggerPriceRefresh, triggerTickerRefresh, setRefreshInterval as apiSetRefreshInterval, getZerodhaStatus, setZerodhaToken } from './services/api';
import Dashboard from './components/Dashboard';
import PortfolioTable from './components/PortfolioTable';
import StockSummaryTable from './components/StockSummaryTable';
import AddStockModal from './components/AddStockModal';
import SellStockModal from './components/SellStockModal';
import TransactionHistory from './components/TransactionHistory';
import Charts from './components/Charts';
import MarketTicker from './components/MarketTicker';
import DividendModal from './components/DividendModal';

export const formatINR = (num) => {
  if (num === null || num === undefined) return '₹0';
  return '₹' + Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function App() {
  const [portfolio, setPortfolio] = useState([]);
  const [stockSummary, setStockSummary] = useState([]);
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('stocks');
  const [addModalData, setAddModalData] = useState(null); // null = closed, {} = open empty, {symbol,...} = pre-filled
  const [sellTarget, setSellTarget] = useState(null);
  const [dividendTarget, setDividendTarget] = useState(null); // {symbol, exchange}
  const [marketTicker, setMarketTicker] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(300); // seconds
  const [zerodhaStatus, setZerodhaStatus] = useState(null); // {configured, has_access_token, session_valid}
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenInput, setTokenInput] = useState('');

  // Read cached data from backend (fast, no external calls)
  // Uses allSettled so one failing endpoint doesn't block the rest
  const loadData = useCallback(async () => {
    try {
      const [pResult, sResult, tResult, ssResult] = await Promise.allSettled([
        getPortfolio(),
        getDashboardSummary(),
        getTransactions(),
        getStockSummary(),
      ]);
      if (pResult.status === 'fulfilled') setPortfolio(pResult.value);
      else console.error('Portfolio load failed:', pResult.reason);

      if (sResult.status === 'fulfilled') setSummary(sResult.value);
      else console.error('Summary load failed:', sResult.reason);

      if (tResult.status === 'fulfilled') setTransactions(tResult.value);
      else console.error('Transactions load failed:', tResult.reason);

      if (ssResult.status === 'fulfilled') setStockSummary(ssResult.value);
      else console.error('Stock summary load failed:', ssResult.reason);

      // Show toast only if ALL failed
      const allFailed = [pResult, sResult, tResult, ssResult].every(r => r.status === 'rejected');
      if (allFailed) toast.error('Failed to load portfolio data');
    } catch (err) {
      console.error('Failed to load data:', err);
      toast.error('Failed to load portfolio data');
    } finally {
      setLoading(false);
    }
    // Load market ticker + Zerodha status separately (non-blocking)
    try {
      const tickerData = await getMarketTicker();
      setMarketTicker(tickerData);
    } catch (err) {
      console.error('Failed to load market ticker:', err);
    }
    try {
      const zs = await getZerodhaStatus();
      setZerodhaStatus(zs);
    } catch (err) {
      console.error('Failed to load Zerodha status:', err);
    }
  }, []);

  // Trigger actual live refresh from external sources (Zerodha/Yahoo/Google)
  // then read updated data
  const liveRefresh = useCallback(async () => {
    try {
      // Fire both live refreshes in parallel
      await Promise.all([
        triggerPriceRefresh().catch(e => console.error('Price refresh error:', e)),
        triggerTickerRefresh().catch(e => console.error('Ticker refresh error:', e)),
      ]);
    } catch (err) {
      console.error('Live refresh error:', err);
    }
    // Now read the updated data
    await loadData();
  }, [loadData]);

  // On mount: read cached data immediately, then trigger first live refresh
  useEffect(() => {
    loadData();             // instant read from cache
    liveRefresh();          // then trigger actual live fetch in background
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh: trigger live refresh at chosen interval
  useEffect(() => {
    const interval = setInterval(liveRefresh, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [liveRefresh, refreshInterval]);

  const handleAddStock = async (data) => {
    try {
      await addStock(data);
      toast.success(`Added ${data.quantity} shares of ${data.symbol}`);
      setAddModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add stock');
    }
  };

  const handleSellStock = async (data) => {
    try {
      const result = await sellStock(data);
      const plText = result.realized_pl >= 0
        ? `Profit: ${formatINR(result.realized_pl)}`
        : `Loss: ${formatINR(Math.abs(result.realized_pl))}`;
      toast.success(`Sold! ${plText}`);
      setSellTarget(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to sell stock');
    }
  };

  const handleAddDividend = async (data) => {
    try {
      const result = await addDividend(data);
      toast.success(result.message);
      setDividendTarget(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to record dividend');
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    await liveRefresh();
    toast.success('Prices refreshed from live sources');
  };

  const handleIntervalChange = async (e) => {
    const newInterval = Number(e.target.value);
    setRefreshInterval(newInterval);
    try {
      await apiSetRefreshInterval(newInterval);
    } catch (err) {
      console.error('Failed to set refresh interval:', err);
    }
  };

  const handleSetToken = async () => {
    if (!tokenInput.trim()) return;
    try {
      const result = await setZerodhaToken(tokenInput.trim());
      toast.success(result.message || 'Token set');
      setShowTokenInput(false);
      setTokenInput('');
      const zs = await getZerodhaStatus();
      setZerodhaStatus(zs);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to set token');
    }
  };

  return (
    <div className="app">
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: '#1a1d27', color: '#e4e6ed', border: '1px solid #2a2d3a' },
          success: { iconTheme: { primary: '#00d26a', secondary: '#1a1d27' } },
          error: { iconTheme: { primary: '#ff4757', secondary: '#1a1d27' } },
        }}
      />

      {/* Market Ticker */}
      <MarketTicker tickers={marketTicker} loading={loading} />

      {/* Header */}
      <header className="header">
        <h1><span>Stock</span> Portfolio Dashboard</h1>
        <div className="header-actions">
          {/* Zerodha status */}
          {zerodhaStatus && (
            <div className="zerodha-status" title={
              zerodhaStatus.session_valid
                ? 'Zerodha connected — live prices active'
                : zerodhaStatus.auth_failed
                  ? 'Zerodha token expired — click to refresh'
                  : zerodhaStatus.has_access_token
                    ? 'Zerodha token set — testing...'
                    : 'Zerodha not connected — click to setup'
            }>
              <a
                className={`zerodha-dot ${
                  zerodhaStatus.session_valid ? 'connected' :
                  zerodhaStatus.auth_failed ? 'expired' : 'disconnected'
                }`}
                href="/api/zerodha/login"
                target="_blank"
                rel="noopener noreferrer"
              >
                Z
              </a>
            </div>
          )}
          <div className="refresh-control">
            <select
              className="refresh-select"
              value={refreshInterval}
              onChange={handleIntervalChange}
              title="Auto-refresh interval"
            >
              <option value={60}>1 min</option>
              <option value={120}>2 min</option>
              <option value={300}>5 min</option>
              <option value={600}>10 min</option>
            </select>
          </div>
          <button className="btn btn-ghost" onClick={handleRefresh} disabled={loading}>
            {loading ? '⟳ Loading...' : '⟳ Refresh'}
          </button>
          <button className="btn btn-primary" onClick={() => setAddModalData({})}>
            + Add Stock
          </button>
        </div>
      </header>

      {/* Dashboard Summary */}
      <Dashboard summary={summary} loading={loading} />

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'stocks' ? 'active' : ''}`} onClick={() => setActiveTab('stocks')}>
          Stocks
        </button>
        <button className={`tab ${activeTab === 'holdings' ? 'active' : ''}`} onClick={() => setActiveTab('holdings')}>
          All Lots
        </button>
        <button className={`tab ${activeTab === 'charts' ? 'active' : ''}`} onClick={() => setActiveTab('charts')}>
          Charts
        </button>
        <button className={`tab ${activeTab === 'transactions' ? 'active' : ''}`} onClick={() => setActiveTab('transactions')}>
          Transactions
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'stocks' && (
        <StockSummaryTable
          stocks={stockSummary}
          loading={loading}
          portfolio={portfolio}
          transactions={transactions}
          onSell={(holding) => setSellTarget(holding)}
          onAddStock={(stockData) => setAddModalData(stockData || {})}
          onDividend={(data) => setDividendTarget(data)}
        />
      )}

      {activeTab === 'holdings' && (
        <PortfolioTable
          portfolio={portfolio}
          loading={loading}
          onSell={(holding) => setSellTarget(holding)}
          onAddStock={() => setAddModalData({})}
        />
      )}

      {activeTab === 'charts' && (
        <Charts portfolio={portfolio} summary={summary} transactions={transactions} />
      )}

      {activeTab === 'transactions' && (
        <TransactionHistory transactions={transactions} />
      )}

      {/* Modals */}
      {addModalData !== null && (
        <AddStockModal
          initialData={addModalData}
          onAdd={handleAddStock}
          onClose={() => setAddModalData(null)}
        />
      )}

      {sellTarget && (
        <SellStockModal
          holding={sellTarget}
          onSell={handleSellStock}
          onClose={() => setSellTarget(null)}
        />
      )}

      {dividendTarget && (
        <DividendModal
          symbol={dividendTarget.symbol}
          exchange={dividendTarget.exchange}
          onSubmit={handleAddDividend}
          onClose={() => setDividendTarget(null)}
        />
      )}
    </div>
  );
}
