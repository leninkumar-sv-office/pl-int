import React, { useState, useEffect, useCallback } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { getPortfolio, getDashboardSummary, getTransactions, addStock, sellStock, addDividend, getStockSummary, getMarketTicker, triggerPriceRefresh, triggerTickerRefresh, setRefreshInterval as apiSetRefreshInterval, getZerodhaStatus, setZerodhaToken, parseContractNote, confirmImportContractNote, getMFSummary, getMFDashboard, addMFHolding, redeemMFUnits, getSIPConfigs, addSIPConfig, deleteSIPConfig, executeSIP, getFDSummary, getFDDashboard, addFD, updateFD, deleteFD, getRDSummary, getRDDashboard, addRD, updateRD, deleteRD, addRDInstallment, getInsuranceSummary, getInsuranceDashboard, addInsurance, updateInsurance, deleteInsurance, getPPFSummary, getPPFDashboard, addPPF, updatePPF, deletePPF, addPPFContribution } from './services/api';
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
import MutualFundTable from './components/MutualFundTable';
import AddMFModal from './components/AddMFModal';
import RedeemMFModal from './components/RedeemMFModal';
import SIPConfigModal from './components/SIPConfigModal';
import FixedDepositTable from './components/FixedDepositTable';
import AddFDModal from './components/AddFDModal';
import RecurringDepositTable from './components/RecurringDepositTable';
import AddRDModal from './components/AddRDModal';
import InsuranceTable from './components/InsuranceTable';
import AddInsuranceModal from './components/AddInsuranceModal';
import PPFTable from './components/PPFTable';
import AddPPFModal from './components/AddPPFModal';

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
  const [bulkSellDoneKey, setBulkSellDoneKey] = useState(0); // increments to signal selection clear
  const [marketTicker, setMarketTicker] = useState([]);
  const [refreshInterval, setRefreshInterval] = useState(300); // seconds
  const [zerodhaStatus, setZerodhaStatus] = useState(null); // {configured, has_access_token, session_valid}
  const [showTokenInput, setShowTokenInput] = useState(false);
  const [tokenInput, setTokenInput] = useState('');
  const [importPreview, setImportPreview] = useState(null); // parsed contract note preview
  const [importResult, setImportResult] = useState(null);   // persistent banner after import
  const [mfSummary, setMfSummary] = useState([]);           // mutual fund per-fund summaries
  const [mfDashboard, setMfDashboard] = useState(null);     // mutual fund dashboard totals
  const [addMFModalData, setAddMFModalData] = useState(null); // null=closed, {}=open, {fund_code,...}=prefill
  const [redeemTarget, setRedeemTarget] = useState(null);     // null=closed, {fund_code, name, ...}=open
  const [sipTarget, setSipTarget] = useState(null);           // null=closed, {fund_code, name, ...}=SIP config
  const [sipConfigs, setSipConfigs] = useState([]);           // SIP configuration list

  // FD / RD / Insurance states
  const [fdSummary, setFdSummary] = useState([]);
  const [fdDashboard, setFdDashboard] = useState(null);
  const [addFDModalData, setAddFDModalData] = useState(null);     // null=closed, {}=add, {id,...}=edit
  const [rdSummary, setRdSummary] = useState([]);
  const [rdDashboard, setRdDashboard] = useState(null);
  const [addRDModalData, setAddRDModalData] = useState(null);     // null=closed, {}=add, {id,...}=edit
  const [rdModalMode, setRdModalMode] = useState('add');          // 'add' | 'edit' | 'installment'
  const [insurancePolicies, setInsurancePolicies] = useState([]);
  const [insuranceDashboard, setInsuranceDashboard] = useState(null);
  const [addInsuranceModalData, setAddInsuranceModalData] = useState(null);

  // PPF states
  const [ppfAccounts, setPpfAccounts] = useState([]);
  const [ppfDashboard, setPpfDashboard] = useState(null);
  const [addPPFModalData, setAddPPFModalData] = useState(null);
  const [ppfModalMode, setPpfModalMode] = useState('add');  // 'add' | 'edit' | 'contribution'

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
    // Load market ticker + Zerodha status + MF data separately (non-blocking)
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
    // Mutual fund data + SIP configs (non-blocking)
    try {
      const [mfSumResult, mfDashResult, sipResult] = await Promise.allSettled([
        getMFSummary(),
        getMFDashboard(),
        getSIPConfigs(),
      ]);
      if (mfSumResult.status === 'fulfilled') setMfSummary(mfSumResult.value);
      if (mfDashResult.status === 'fulfilled') setMfDashboard(mfDashResult.value);
      if (sipResult.status === 'fulfilled') setSipConfigs(sipResult.value);
    } catch (err) {
      console.error('Failed to load MF data:', err);
    }
    // FD / RD / Insurance / PPF data (non-blocking)
    try {
      const [fdSumR, fdDashR, rdSumR, rdDashR, insSumR, insDashR, ppfSumR, ppfDashR] = await Promise.allSettled([
        getFDSummary(), getFDDashboard(),
        getRDSummary(), getRDDashboard(),
        getInsuranceSummary(), getInsuranceDashboard(),
        getPPFSummary(), getPPFDashboard(),
      ]);
      if (fdSumR.status === 'fulfilled') setFdSummary(fdSumR.value);
      if (fdDashR.status === 'fulfilled') setFdDashboard(fdDashR.value);
      if (rdSumR.status === 'fulfilled') setRdSummary(rdSumR.value);
      if (rdDashR.status === 'fulfilled') setRdDashboard(rdDashR.value);
      if (insSumR.status === 'fulfilled') setInsurancePolicies(insSumR.value);
      if (insDashR.status === 'fulfilled') setInsuranceDashboard(insDashR.value);
      if (ppfSumR.status === 'fulfilled') setPpfAccounts(ppfSumR.value);
      if (ppfDashR.status === 'fulfilled') setPpfDashboard(ppfDashR.value);
    } catch (err) {
      console.error('Failed to load FD/RD/Insurance/PPF data:', err);
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

  const handleBulkSellClose = (result) => {
    setBulkSellItems(null);
    setBulkSellDoneKey(k => k + 1); // signal StockSummaryTable to clear selection
    loadData();
    if (!result) return; // manual close via Cancel
    if (result.failed === 0) {
      toast.success(`Sold ${result.succeeded} lot${result.succeeded !== 1 ? 's' : ''} successfully`);
    } else if (result.succeeded === 0) {
      toast.error(`All ${result.failed} sell operation${result.failed !== 1 ? 's' : ''} failed`);
    } else {
      toast.success(`${result.succeeded} sold, ${result.failed} failed`);
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

      let totalBuys = 0, totalSells = 0, totalDupsSkipped = 0;
      const allErrors = [];
      const allBuyDetails = [];
      const allSellDetails = [];
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
        totalDupsSkipped += result.skipped_duplicates || 0;
        if (result.imported?.buy_details) {
          result.imported.buy_details.forEach(d => {
            d.trade_date = group.trade_date;
          });
          allBuyDetails.push(...result.imported.buy_details);
        }
        if (result.imported?.sell_details) {
          result.imported.sell_details.forEach(d => {
            d.trade_date = group.trade_date;
          });
          allSellDetails.push(...result.imported.sell_details);
        }
        if (result.errors) allErrors.push(...result.errors);
      }

      toast.dismiss('import-progress');

      // Build persistent result banner data with full details
      const resultData = {
        totalBuys,
        totalSells,
        totalDupsSkipped,
        buyDetails: allBuyDetails,
        sellDetails: allSellDetails,
        errors: allErrors,
        tradeDate: importPreview.trade_date,
        batchCount: batchKeys.length,
        timestamp: new Date().toLocaleTimeString(),
      };
      setImportResult(resultData);
      setImportPreview(null);
      loadData();
    } catch (err) {
      toast.dismiss('import-progress');
      const msg = err.response?.data?.detail || 'Failed to import contract note';
      toast.error(msg, { duration: 5000 });
    }
  };

  // ── Mutual Fund handlers ────────────────────────
  const handleAddMFHolding = async (data) => {
    try {
      await addMFHolding(data);
      toast.success(`Added ${data.units} units of ${data.fund_name}`);
      setAddMFModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add MF holding');
    }
  };

  const handleRedeemMF = async (data) => {
    try {
      const result = await redeemMFUnits(data);
      const plText = result.realized_pl >= 0
        ? `Profit: ${formatINR(result.realized_pl)}`
        : `Loss: ${formatINR(Math.abs(result.realized_pl))}`;
      toast.success(`Redeemed! ${plText}`);
      setRedeemTarget(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to redeem MF');
    }
  };

  const handleSaveSIP = async (config) => {
    try {
      await addSIPConfig(config);
      toast.success(`SIP configured for ${config.fund_name}`);
      setSipTarget(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save SIP config');
    }
  };

  const handleDeleteSIP = async (fundCode) => {
    try {
      await deleteSIPConfig(fundCode);
      toast.success('SIP removed');
      setSipTarget(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete SIP');
    }
  };

  const handleExecuteSIP = async (fundCode) => {
    try {
      const result = await executeSIP(fundCode);
      toast.success(result.message || 'SIP executed');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to execute SIP');
    }
  };

  // ── Fixed Deposit handlers ────────────────────────
  const handleAddFD = async (data) => {
    try {
      if (data.id) {
        await updateFD(data.id, data);
        toast.success('FD updated');
      } else {
        await addFD(data);
        toast.success(`Added FD at ${data.bank}`);
      }
      setAddFDModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save FD');
    }
  };

  const handleDeleteFD = async (fdId) => {
    try {
      await deleteFD(fdId);
      toast.success('FD deleted');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete FD');
    }
  };

  // ── Recurring Deposit handlers ────────────────────
  const handleAddRD = async (data) => {
    try {
      if (data.rd_id) {
        // Adding installment
        await addRDInstallment(data.rd_id, { date: data.date, amount: data.amount, remarks: data.remarks });
        toast.success('Installment added');
      } else if (data.id) {
        await updateRD(data.id, data);
        toast.success('RD updated');
      } else {
        await addRD(data);
        toast.success(`Added RD at ${data.bank}`);
      }
      setAddRDModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save RD');
    }
  };

  const handleDeleteRD = async (rdId) => {
    try {
      await deleteRD(rdId);
      toast.success('RD deleted');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete RD');
    }
  };

  // ── Insurance handlers ────────────────────────────
  const handleAddInsurance = async (data) => {
    try {
      if (data.id) {
        await updateInsurance(data.id, data);
        toast.success('Policy updated');
      } else {
        await addInsurance(data);
        toast.success(`Added policy: ${data.policy_name}`);
      }
      setAddInsuranceModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save policy');
    }
  };

  const handleDeleteInsurance = async (policyId) => {
    try {
      await deleteInsurance(policyId);
      toast.success('Policy deleted');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete policy');
    }
  };

  // ── PPF handlers ────────────────────────────────
  const handleAddPPF = async (data) => {
    try {
      if (data.ppf_id) {
        // Adding contribution
        await addPPFContribution(data.ppf_id, { date: data.date, amount: data.amount, remarks: data.remarks });
        toast.success('Contribution added');
      } else if (data.id) {
        await updatePPF(data.id, data);
        toast.success('PPF account updated');
      } else {
        await addPPF(data);
        toast.success(`Added PPF account: ${data.account_name}`);
      }
      setAddPPFModalData(null);
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save PPF');
    }
  };

  const handleDeletePPF = async (ppfId) => {
    try {
      await deletePPF(ppfId);
      toast.success('PPF account deleted');
      loadData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete PPF');
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

      {/* Persistent Import Result Banner */}
      {importResult && (() => {
        const hasErrors = importResult.errors.length > 0;
        const hasNone = importResult.totalBuys === 0 && importResult.totalSells === 0;
        const borderColor = hasErrors ? 'rgba(255,71,87,0.3)' : 'rgba(0,210,106,0.3)';
        const bgGrad = hasErrors
          ? 'linear-gradient(90deg, rgba(255,71,87,0.12) 0%, rgba(255,71,87,0.04) 100%)'
          : 'linear-gradient(90deg, rgba(0,210,106,0.12) 0%, rgba(0,210,106,0.04) 100%)';
        const _fmt = (n) => '₹' + Number(n || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        const detailTh = { padding: '4px 10px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.4px', color: 'var(--text-muted)', fontWeight: 600, textAlign: 'left', borderBottom: '1px solid var(--border)' };
        const detailTd = { padding: '5px 10px', fontSize: '12px', borderBottom: '1px solid rgba(255,255,255,0.04)' };
        return (
          <div style={{
            background: bgGrad,
            border: `1px solid ${borderColor}`,
            borderRadius: '8px',
            margin: '8px 16px',
            animation: 'fadeIn 0.3s ease-in',
            overflow: 'hidden',
          }}>
            {/* Header row */}
            <div style={{
              padding: '12px 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <span style={{ fontSize: '18px', lineHeight: 1 }}>
                  {hasErrors ? '⚠' : '✓'}
                </span>
                <div>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text)' }}>
                    Import Complete
                    <span style={{ fontWeight: 400, fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                      at {importResult.timestamp}
                    </span>
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-dim)', marginTop: '2px', display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                    {importResult.totalBuys > 0 && (
                      <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                        {importResult.totalBuys} buy{importResult.totalBuys !== 1 ? 's' : ''}
                      </span>
                    )}
                    {importResult.totalBuys > 0 && importResult.totalSells > 0 && <span>,</span>}
                    {importResult.totalSells > 0 && (
                      <span style={{ color: '#f59e0b', fontWeight: 600 }}>
                        {importResult.totalSells} sell{importResult.totalSells !== 1 ? 's' : ''}
                      </span>
                    )}
                    {hasNone && <span style={{ color: 'var(--text-muted)' }}>No transactions imported</span>}
                    <span style={{ color: 'var(--text-muted)' }}>
                      {importResult.batchCount > 1
                        ? `from ${importResult.batchCount} contract notes`
                        : `from ${importResult.tradeDate}`}
                    </span>
                    {importResult.totalDupsSkipped > 0 && (
                      <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                        ({importResult.totalDupsSkipped} duplicate{importResult.totalDupsSkipped !== 1 ? 's' : ''} skipped)
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                onClick={() => setImportResult(null)}
                style={{
                  background: 'none',
                  border: '1px solid var(--border)',
                  borderRadius: '6px',
                  color: 'var(--text-dim)',
                  padding: '4px 12px',
                  fontSize: '12px',
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                  flexShrink: 0,
                }}
                title="Dismiss this notification"
              >
                ✕ Dismiss
              </button>
            </div>

            {/* Detail tables */}
            {(!hasNone) && (
              <div style={{ padding: '0 20px 14px', display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
                {/* Buys table */}
                {importResult.buyDetails.length > 0 && (
                  <div style={{ flex: '1 1 300px', minWidth: '280px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--green)', marginBottom: '6px' }}>
                      Buys ({importResult.buyDetails.length})
                    </div>
                    <div style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                            <th style={detailTh}>Stock</th>
                            <th style={{ ...detailTh, textAlign: 'right' }}>Qty</th>
                            <th style={{ ...detailTh, textAlign: 'right' }}>Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importResult.buyDetails.map((d, i) => (
                            <tr key={`b-${i}`}>
                              <td style={detailTd}>
                                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{d.symbol}</span>
                                {d.name && d.name !== d.symbol && (
                                  <span style={{ color: 'var(--text-muted)', marginLeft: '6px', fontSize: '11px' }}>{d.name}</span>
                                )}
                              </td>
                              <td style={{ ...detailTd, textAlign: 'right', fontWeight: 600, color: 'var(--green)' }}>
                                +{d.quantity}
                              </td>
                              <td style={{ ...detailTd, textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>
                                {d.trade_date || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {/* Sells table */}
                {importResult.sellDetails.length > 0 && (
                  <div style={{ flex: '1 1 300px', minWidth: '280px' }}>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#f59e0b', marginBottom: '6px' }}>
                      Sells ({importResult.sellDetails.length})
                    </div>
                    <div style={{ border: '1px solid var(--border)', borderRadius: '6px', overflow: 'hidden' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                            <th style={detailTh}>Stock</th>
                            <th style={{ ...detailTh, textAlign: 'right' }}>Qty</th>
                            <th style={{ ...detailTh, textAlign: 'right' }}>Date</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importResult.sellDetails.map((d, i) => (
                            <tr key={`s-${i}`}>
                              <td style={detailTd}>
                                <span style={{ fontWeight: 600, color: 'var(--text)' }}>{d.symbol}</span>
                                {d.name && d.name !== d.symbol && (
                                  <span style={{ color: 'var(--text-muted)', marginLeft: '6px', fontSize: '11px' }}>{d.name}</span>
                                )}
                              </td>
                              <td style={{ ...detailTd, textAlign: 'right', fontWeight: 600, color: '#f59e0b' }}>
                                -{d.quantity}
                              </td>
                              <td style={{ ...detailTd, textAlign: 'right', color: 'var(--text-muted)', fontSize: '11px' }}>
                                {d.trade_date || '-'}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Errors section */}
            {hasErrors && (
              <div style={{ padding: '0 20px 14px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--red)', marginBottom: '4px' }}>
                  Errors ({importResult.errors.length})
                </div>
                <div style={{ fontSize: '12px', color: 'var(--red)', opacity: 0.85 }}>
                  {importResult.errors.map((e, i) => (
                    <div key={i} style={{ marginBottom: '2px' }}>• {e}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })()}

      {/* Header */}
      <header className="header">
        <h1><span>Portfolio</span> Dashboard</h1>
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
          {activeTab === 'mutualfunds' ? (
            <button className="btn btn-primary" onClick={() => setAddMFModalData({})}>
              + Buy MF
            </button>
          ) : activeTab === 'fixeddeposits' ? (
            <button className="btn btn-primary" onClick={() => setAddFDModalData({})}>
              + Add FD
            </button>
          ) : activeTab === 'recurringdeposits' ? (
            <button className="btn btn-primary" onClick={() => { setRdModalMode('add'); setAddRDModalData({}); }}>
              + Add RD
            </button>
          ) : activeTab === 'insurance' ? (
            <button className="btn btn-primary" onClick={() => setAddInsuranceModalData({})}>
              + Add Policy
            </button>
          ) : activeTab === 'ppf' ? (
            <button className="btn btn-primary" onClick={() => { setPpfModalMode('add'); setAddPPFModalData({}); }}>
              + Add PPF
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => setAddModalData({})}>
              + Add Stock
            </button>
          )}
        </div>
      </header>

      {/* Dashboard Summary — combined Stocks + MF */}
      <Dashboard summary={summary} mfDashboard={mfDashboard} loading={loading} />

      {/* Market Ticker */}
      <MarketTicker tickers={marketTicker} loading={loading} />

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'stocks' ? 'active' : ''}`} onClick={() => setActiveTab('stocks')}>
          Stocks
        </button>
        <button className={`tab ${activeTab === 'mutualfunds' ? 'active' : ''}`} onClick={() => setActiveTab('mutualfunds')}>
          Mutual Funds
        </button>
        <button className={`tab ${activeTab === 'fixeddeposits' ? 'active' : ''}`} onClick={() => setActiveTab('fixeddeposits')}>
          Fixed Deposits
        </button>
        <button className={`tab ${activeTab === 'recurringdeposits' ? 'active' : ''}`} onClick={() => setActiveTab('recurringdeposits')}>
          Recurring Deposits
        </button>
        <button className={`tab ${activeTab === 'insurance' ? 'active' : ''}`} onClick={() => setActiveTab('insurance')}>
          Insurance
        </button>
        <button className={`tab ${activeTab === 'ppf' ? 'active' : ''}`} onClick={() => setActiveTab('ppf')}>
          PPF
        </button>
        <button className={`tab ${activeTab === 'charts' ? 'active' : ''}`} onClick={() => setActiveTab('charts')}>
          Charts
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
          bulkSellDoneKey={bulkSellDoneKey}
        />
      )}

      {activeTab === 'charts' && (
        <Charts portfolio={portfolio} summary={summary} transactions={transactions} />
      )}

      {activeTab === 'mutualfunds' && (
        <MutualFundTable
          funds={mfSummary}
          loading={loading}
          mfDashboard={mfDashboard}
          onBuyMF={(fundData) => setAddMFModalData(fundData || {})}
          onRedeemMF={(fund) => setRedeemTarget(fund)}
          onConfigSIP={(fund) => setSipTarget(fund)}
          sipConfigs={sipConfigs}
        />
      )}

      {activeTab === 'fixeddeposits' && (
        <FixedDepositTable
          deposits={fdSummary}
          loading={loading}
          fdDashboard={fdDashboard}
          onAddFD={() => setAddFDModalData({})}
          onEditFD={(fd) => setAddFDModalData(fd)}
          onDeleteFD={handleDeleteFD}
        />
      )}

      {activeTab === 'recurringdeposits' && (
        <RecurringDepositTable
          deposits={rdSummary}
          loading={loading}
          rdDashboard={rdDashboard}
          onAddRD={() => { setRdModalMode('add'); setAddRDModalData({}); }}
          onEditRD={(rd) => { setRdModalMode('edit'); setAddRDModalData(rd); }}
          onDeleteRD={handleDeleteRD}
          onAddInstallment={(rd) => { setRdModalMode('installment'); setAddRDModalData(rd); }}
        />
      )}

      {activeTab === 'insurance' && (
        <InsuranceTable
          policies={insurancePolicies}
          loading={loading}
          insuranceDashboard={insuranceDashboard}
          onAddInsurance={() => setAddInsuranceModalData({})}
          onEditInsurance={(p) => setAddInsuranceModalData(p)}
          onDeleteInsurance={handleDeleteInsurance}
        />
      )}

      {activeTab === 'ppf' && (
        <PPFTable
          accounts={ppfAccounts}
          loading={loading}
          ppfDashboard={ppfDashboard}
          onAddPPF={() => { setPpfModalMode('add'); setAddPPFModalData({}); }}
          onEditPPF={(ppf) => { setPpfModalMode('edit'); setAddPPFModalData(ppf); }}
          onDeletePPF={handleDeletePPF}
          onAddContribution={(ppf) => { setPpfModalMode('contribution'); setAddPPFModalData(ppf); }}
        />
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

      {/* MF Modals */}
      {addMFModalData !== null && (
        <AddMFModal
          initialData={addMFModalData}
          funds={mfSummary}
          onAdd={handleAddMFHolding}
          onClose={() => setAddMFModalData(null)}
        />
      )}

      {redeemTarget && (
        <RedeemMFModal
          fund={redeemTarget}
          onRedeem={handleRedeemMF}
          onClose={() => setRedeemTarget(null)}
        />
      )}

      {sipTarget && (
        <SIPConfigModal
          fund={sipTarget}
          existingSIP={sipConfigs.find(s => s.fund_code === sipTarget.fund_code)}
          onSave={handleSaveSIP}
          onDelete={handleDeleteSIP}
          onClose={() => setSipTarget(null)}
        />
      )}

      {/* FD Modal */}
      {addFDModalData !== null && (
        <AddFDModal
          initialData={addFDModalData}
          onAdd={handleAddFD}
          onClose={() => setAddFDModalData(null)}
        />
      )}

      {/* RD Modal (add / edit / installment) */}
      {addRDModalData !== null && (
        <AddRDModal
          initialData={addRDModalData}
          mode={rdModalMode}
          onAdd={handleAddRD}
          onClose={() => setAddRDModalData(null)}
        />
      )}

      {/* Insurance Modal */}
      {addInsuranceModalData !== null && (
        <AddInsuranceModal
          initialData={addInsuranceModalData}
          onAdd={handleAddInsurance}
          onClose={() => setAddInsuranceModalData(null)}
        />
      )}

      {/* PPF Modal (add / edit / contribution) */}
      {addPPFModalData !== null && (
        <AddPPFModal
          initialData={addPPFModalData}
          mode={ppfModalMode}
          onSubmit={handleAddPPF}
          onClose={() => setAddPPFModalData(null)}
        />
      )}
    </div>
  );
}
