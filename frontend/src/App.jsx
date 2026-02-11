import React, { useState, useEffect, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { getPortfolio, getDashboardSummary, getTransactions, addStock, sellStock, addDividend, getStockSummary, getMarketTicker, triggerPriceRefresh, triggerTickerRefresh, setRefreshInterval as apiSetRefreshInterval, getZerodhaStatus, setZerodhaToken, parseContractNote, confirmImportContractNote } from './services/api';
import Dashboard from './components/Dashboard';
import PortfolioTable from './components/PortfolioTable';
import StockSummaryTable from './components/StockSummaryTable';
import AddStockModal from './components/AddStockModal';
import SellStockModal from './components/SellStockModal';
import BulkSellModal from './components/BulkSellModal';
import TransactionHistory from './components/TransactionHistory';
import Charts from './components/Charts';
import MarketTicker from './components/MarketTicker';
import DividendModal from './components/DividendModal';
import ImportPreviewModal from './components/ImportPreviewModal';

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
  const [bulkSellItems, setBulkSellItems] = useState(null); // null = closed, [...] = open
  const [marketTicker, setMarketTicker] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(300); // seconds
  const [zerodhaStatus, setZerodhaStatus] = useState(null); // {configured, has_access_token, session_valid}
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [importPreview, setImportPreview] = useState(null); // parsed contract note preview

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

      // Show toast with details on which endpoints failed
      const results = [
        { name: 'Portfolio', r: pResult },
        { name: 'Summary', r: sResult },
        { name: 'Transactions', r: tResult },
        { name: 'Stocks', r: ssResult },
      ];
      const failed = results.filter(x => x.r.status === 'rejected');
      if (failed.length === results.length) {
        const reason = failed[0].r.reason?.message || 'Server unreachable';
        toast.error(`Failed to load data: ${reason}`);
      } else if (failed.length > 0) {
        const names = failed.map(x => x.name).join(', ');
        toast.error(`Failed to load: ${names}`);
      }
    } catch (err) {
      console.error('Failed to load data:', err);
      toast.error(`Failed to load portfolio data: ${err.message || err}`);
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

  // On mount: read cached data first, THEN trigger live refresh after data loads
  useEffect(() => {
    let mounted = true;
    (async () => {
      await loadData();                    // read cached data first (instant)
      if (mounted) {
        // Small delay to let backend threads settle before triggering live refresh
        setTimeout(() => { if (mounted) liveRefresh(); }, 500);
      }
    })();
    return () => { mounted = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-refresh: trigger live refresh at chosen interval
  useEffect(() => {
    const interval = setInterval(liveRefresh, refreshInterval * 1000);
    return () => clearInterval(interval);
  }, [liveRefresh, refreshInterval]);

  // Re-fetch Zerodha status + data when user returns to this tab
  // (e.g. after completing Zerodha login in another tab)
  useEffect(() => {
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        getZerodhaStatus().then(zs => setZerodhaStatus(zs)).catch(() => {});
        liveRefresh();
      }
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, [liveRefresh]);

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

  const handleBulkSellSingle = async (data) => {
    // Sell a single lot — called repeatedly by BulkSellModal
    const result = await sellStock(data);
    return result;
  };

  const handleBulkSellClose = () => {
    setBulkSellItems(null);
    loadData();
    toast.success('Bulk sell completed');
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

  // Step 1: Parse PDF(s) → show preview modal
  // Accepts an array of File objects (multi-select) or a single File (legacy)
  const handleParseContractNote = async (filesOrFile) => {
    const files = Array.isArray(filesOrFile) ? filesOrFile : [filesOrFile];
    try {
      const allParsed = [];
      const errors = [];

      // Parse each PDF sequentially (backend handles one at a time)
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
          if (files.length > 1) {
            toast.loading(`Parsing PDF ${i + 1}/${files.length}: ${file.name}`, { id: 'pdf-parse-progress' });
          }
          const parsed = await parseContractNote(file);
          if (parsed.summary.total > 0) {
            // Tag each transaction with its source file for display
            parsed.transactions.forEach(tx => {
              tx._sourceFile = file.name;
              tx._contractNo = parsed.contract_no || '';
            });
            allParsed.push(parsed);
          } else {
            errors.push(`${file.name}: No transactions found`);
          }
        } catch (err) {
          const msg = err.response?.data?.detail || 'Parse failed';
          errors.push(`${file.name}: ${msg}`);
        }
      }

      toast.dismiss('pdf-parse-progress');

      if (errors.length > 0) {
        toast.error(errors.join('\n'), { duration: 8000 });
      }

      if (allParsed.length === 0) {
        if (errors.length === 0) {
          toast.error('No transactions found in any PDF.', { duration: 8000 });
        }
        return;
      }

      // Merge all parsed results into a single preview
      if (allParsed.length === 1) {
        setImportPreview(allParsed[0]);  // single PDF — same as before
      } else {
        // Combine transactions from all PDFs
        const mergedTransactions = allParsed.flatMap(p => p.transactions);
        const mergedTradeDates = [...new Set(allParsed.map(p => p.trade_date))].sort();
        const mergedContractNos = allParsed.map(p => p.contract_no).filter(Boolean);
        const merged = {
          trade_date: mergedTradeDates.join(', '),
          contract_no: mergedContractNos.join(', '),
          transactions: mergedTransactions,
          summary: {
            buys: mergedTransactions.filter(t => t.action === 'Buy').length,
            sells: mergedTransactions.filter(t => t.action === 'Sell').length,
            total: mergedTransactions.length,
          },
          _multiPdf: true,
          _fileCount: allParsed.length,
        };
        setImportPreview(merged);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Failed to parse contract notes';
      toast.error(msg, { duration: 5000 });
      throw err;
    }
  };

  // Step 2: User confirms → actually import (with possibly edited transactions)
  // For multi-PDF: groups transactions by contract note and sends each batch separately
  const handleConfirmImport = async (editedTransactions) => {
    if (!importPreview) return;
    try {
      const txs = editedTransactions || importPreview.transactions;

      // Group transactions by contract note (source file)
      const groups = {};
      for (const tx of txs) {
        // Use _contractNo + trade_date as group key
        const cn = tx._contractNo || importPreview.contract_no || '';
        const td = tx.trade_date || importPreview.trade_date;
        const key = `${cn}||${td}`;
        if (!groups[key]) groups[key] = { contract_no: cn, trade_date: td, transactions: [] };
        groups[key].transactions.push(tx);
      }

      let totalBuys = 0, totalSells = 0;
      const allErrors = [];
      const batchKeys = Object.keys(groups);

      for (let i = 0; i < batchKeys.length; i++) {
        const group = groups[batchKeys[i]];
        if (batchKeys.length > 1) {
          toast.loading(`Importing batch ${i + 1}/${batchKeys.length}...`, { id: 'import-progress' });
        }
        const result = await confirmImportContractNote({
          trade_date: group.trade_date,
          contract_no: group.contract_no,
          transactions: group.transactions,
        });
        totalBuys += result.imported?.buys || 0;
        totalSells += result.imported?.sells || 0;
        if (result.errors) allErrors.push(...result.errors);
      }

      toast.dismiss('import-progress');
      toast.success(
        `Imported ${totalBuys} buys, ${totalSells} sells` +
        (batchKeys.length > 1 ? ` from ${batchKeys.length} contract notes` : ` from ${importPreview.trade_date}`),
        { duration: 5000 }
      );
      if (allErrors.length > 0) {
        toast.error(`${allErrors.length} error(s): ${allErrors[0]}`, { duration: 5000 });
      }
      setImportPreview(null);
      loadData();
    } catch (err) {
      toast.dismiss('import-progress');
      const msg = err.response?.data?.detail || 'Failed to import contract note';
      toast.error(msg, { duration: 5000 });
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
          onBulkSell={(items) => setBulkSellItems(items)}
          onAddStock={(stockData) => setAddModalData(stockData || {})}
          onDividend={(data) => setDividendTarget(data)}
          onImportContractNote={handleParseContractNote}
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

      {bulkSellItems && (
        <BulkSellModal
          items={bulkSellItems}
          onSell={handleBulkSellSingle}
          onClose={handleBulkSellClose}
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

      {importPreview && (
        <ImportPreviewModal
          data={importPreview}
          existingSymbols={new Set(stockSummary.map(s => s.symbol))}
          onConfirm={handleConfirmImport}
          onCancel={() => setImportPreview(null)}
        />
      )}
    </div>
  );
}
