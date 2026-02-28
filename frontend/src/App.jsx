import React, { useState, useEffect, useCallback, useRef } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { getPortfolio, getDashboardSummary, getTransactions, addStock, sellStock, addDividend, getStockSummary, getMarketTicker, triggerPriceRefresh, triggerTickerRefresh, triggerMFNavRefresh, setRefreshInterval as apiSetRefreshInterval, getZerodhaStatus, setZerodhaToken, parseContractNote, confirmImportContractNote, getMFSummary, getMFDashboard, addMFHolding, redeemMFUnits, getSIPConfigs, addSIPConfig, deleteSIPConfig, executeSIP, parseCDSLCAS, confirmCDSLCASImport, getFDSummary, getFDDashboard, addFD, updateFD, deleteFD, getRDSummary, getRDDashboard, addRD, updateRD, deleteRD, addRDInstallment, getInsuranceSummary, getInsuranceDashboard, addInsurance, updateInsurance, deleteInsurance, getPPFSummary, getPPFDashboard, addPPF, updatePPF, deletePPF, addPPFContribution, withdrawPPF, getNPSSummary, getNPSDashboard, addNPS, updateNPS, deleteNPS, addNPSContribution, getSISummary, getSIDashboard, addSI, updateSI, deleteSI } from './services/api';
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
import NPSTable from './components/NPSTable';
import AddNPSModal from './components/AddNPSModal';
import StandingInstructionTable from './components/StandingInstructionTable';
import AddSIModal from './components/AddSIModal';
import MFImportPreviewModal from './components/MFImportPreviewModal';

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
  const [activeTab, _setActiveTab] = useState(() => localStorage.getItem('activeTab') || 'stocks');
  const setActiveTab = (tab) => { localStorage.setItem('activeTab', tab); _setActiveTab(tab); };
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
  const [mfImportPreview, setMfImportPreview] = useState(null); // CDSL CAS statement preview
  const [mfImportResult, setMfImportResult] = useState(null);   // import result banner

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

  // NPS states
  const [npsAccounts, setNpsAccounts] = useState([]);
  const [npsDashboard, setNpsDashboard] = useState(null);
  const [addNPSModalData, setAddNPSModalData] = useState(null);
  const [npsModalMode, setNpsModalMode] = useState('add');  // 'add' | 'edit' | 'contribution'

  // SI states
  const [siSummary, setSiSummary] = useState([]);
  const [siDashboard, setSiDashboard] = useState(null);
  const [addSIModalData, setAddSIModalData] = useState(null);
  const siAlertedRef = useRef(new Set());

  // ── Independent per-group loaders ─────────────────────
  // Each group fires its API calls and updates state as soon as it resolves,
  // without waiting for other groups. Stocks (slow) no longer block FD/RD/PPF/SI etc.

  const loadStocks = useCallback(async () => {
    const [pR, sR, tR, ssR] = await Promise.allSettled([
      getPortfolio(), getDashboardSummary(), getTransactions(), getStockSummary(),
    ]);
    if (pR.status === 'fulfilled') setPortfolio(pR.value);
    if (sR.status === 'fulfilled') setSummary(sR.value);
    if (tR.status === 'fulfilled') setTransactions(tR.value);
    if (ssR.status === 'fulfilled') setStockSummary(ssR.value);
    const core = [
      { name: 'Portfolio', r: pR }, { name: 'Summary', r: sR },
      { name: 'Transactions', r: tR }, { name: 'Stocks', r: ssR },
    ];
    const failed = core.filter(x => x.r.status === 'rejected');
    if (failed.length === core.length) {
      toast.error(`Failed to load data: ${failed[0].r.reason?.message || 'Server unreachable'}`);
    } else if (failed.length > 0) {
      toast.error(`Failed to load: ${failed.map(x => x.name).join(', ')}`);
    }
  }, []);

  const loadGlobal = useCallback(async () => {
    const [tickR, zsR] = await Promise.allSettled([getMarketTicker(), getZerodhaStatus()]);
    if (tickR.status === 'fulfilled') setMarketTicker(tickR.value);
    if (zsR.status === 'fulfilled') setZerodhaStatus(zsR.value);
  }, []);

  const loadMutualFunds = useCallback(async () => {
    const [mfSumR, mfDashR, sipR] = await Promise.allSettled([
      getMFSummary(), getMFDashboard(), getSIPConfigs(),
    ]);
    if (mfSumR.status === 'fulfilled') setMfSummary(mfSumR.value);
    if (mfDashR.status === 'fulfilled') setMfDashboard(mfDashR.value);
    if (sipR.status === 'fulfilled') setSipConfigs(sipR.value);
  }, []);

  const loadFD = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getFDSummary(), getFDDashboard()]);
    if (sumR.status === 'fulfilled') setFdSummary(sumR.value);
    if (dashR.status === 'fulfilled') setFdDashboard(dashR.value);
  }, []);

  const loadRD = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getRDSummary(), getRDDashboard()]);
    if (sumR.status === 'fulfilled') setRdSummary(sumR.value);
    if (dashR.status === 'fulfilled') setRdDashboard(dashR.value);
  }, []);

  const loadInsurance = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getInsuranceSummary(), getInsuranceDashboard()]);
    if (sumR.status === 'fulfilled') setInsurancePolicies(sumR.value);
    if (dashR.status === 'fulfilled') setInsuranceDashboard(dashR.value);
  }, []);

  const loadPPF = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getPPFSummary(), getPPFDashboard()]);
    if (sumR.status === 'fulfilled') setPpfAccounts(sumR.value);
    if (dashR.status === 'fulfilled') setPpfDashboard(dashR.value);
  }, []);

  const loadNPS = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getNPSSummary(), getNPSDashboard()]);
    if (sumR.status === 'fulfilled') setNpsAccounts(sumR.value);
    if (dashR.status === 'fulfilled') setNpsDashboard(dashR.value);
  }, []);

  const loadSI = useCallback(async () => {
    const [sumR, dashR] = await Promise.allSettled([getSISummary(), getSIDashboard()]);
    if (sumR.status === 'fulfilled') {
      setSiSummary(sumR.value);
      for (const si of sumR.value) {
        if (si.status === 'Active' && si.days_to_expiry > 0 && si.days_to_expiry <= si.alert_days && !siAlertedRef.current.has(si.id)) {
          siAlertedRef.current.add(si.id);
          toast(`SI "${si.beneficiary}" at ${si.bank} expires in ${si.days_to_expiry} days`, { icon: '\u26A0\uFE0F', duration: 6000 });
        }
      }
    }
    if (dashR.status === 'fulfilled') setSiDashboard(dashR.value);
  }, []);

  // Fire ALL groups concurrently — each updates state independently as it resolves
  const loadData = useCallback(async () => {
    try {
      await Promise.allSettled([
        loadStocks(), loadGlobal(), loadMutualFunds(),
        loadFD(), loadRD(), loadInsurance(), loadPPF(), loadNPS(), loadSI(),
      ]);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  }, [loadStocks, loadGlobal, loadMutualFunds, loadFD, loadRD, loadInsurance, loadPPF, loadNPS, loadSI]);

  // Trigger ALL live refreshes in parallel, then reload only affected groups
  const liveRefresh = useCallback(async () => {
    try {
      await Promise.all([
        triggerPriceRefresh().catch(e => console.error('Price refresh error:', e)),
        triggerTickerRefresh().catch(e => console.error('Ticker refresh error:', e)),
        triggerMFNavRefresh().catch(e => console.error('MF NAV refresh error:', e)),
      ]);
    } catch (err) {
      console.error('Live refresh error:', err);
    }
    // Only reload groups affected by price/ticker/NAV refresh
    await Promise.allSettled([loadStocks(), loadGlobal(), loadMutualFunds()]);
  }, [loadStocks, loadGlobal, loadMutualFunds]);

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
      loadStocks();
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
      loadStocks();
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
    loadStocks();
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
      loadStocks();
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
      loadStocks();
    } catch (err) {
      toast.dismiss('import-progress');
      const msg = err.response?.data?.detail || 'Failed to import contract note';
      toast.error(msg, { duration: 5000 });
    }
  };

  // ── CDSL CAS Statement Import ────────────────────────
  // Accepts an array of File objects (multi-select) or a single File
  const handleParseCDSLCAS = async (filesOrFile) => {
    const files = Array.isArray(filesOrFile) ? filesOrFile : [filesOrFile];
    try {
      const allFunds = [];
      const errors = [];
      let casId = '';
      let statementPeriod = '';
      let totalPurchases = 0;
      let totalRedemptions = 0;

      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        try {
          if (files.length > 1) {
            toast.loading(`Parsing PDF ${i + 1}/${files.length}: ${file.name}`, { id: 'cdsl-cas-parse' });
          } else {
            toast.loading('Parsing CDSL CAS statement...', { id: 'cdsl-cas-parse' });
          }
          const parsed = await parseCDSLCAS(file);
          if (parsed.funds && parsed.funds.length > 0) {
            parsed.funds.forEach(f => {
              f.transactions.forEach(tx => { tx._sourceFile = file.name; });
            });
            for (const fund of parsed.funds) {
              const existing = allFunds.find(f => f.fund_code === fund.fund_code);
              if (existing) {
                existing.transactions.push(...fund.transactions);
              } else {
                allFunds.push({ ...fund });
              }
            }
            if (!casId && parsed.cas_id) casId = parsed.cas_id;
            if (parsed.statement_period) {
              statementPeriod = statementPeriod
                ? `${statementPeriod}; ${parsed.statement_period}`
                : parsed.statement_period;
            }
            totalPurchases += parsed.summary?.total_purchases || 0;
            totalRedemptions += parsed.summary?.total_redemptions || 0;
          } else {
            errors.push(`${file.name}: No transactions found`);
          }
        } catch (err) {
          const msg = err.response?.data?.detail || 'Parse failed';
          errors.push(`${file.name}: ${msg}`);
        }
      }

      toast.dismiss('cdsl-cas-parse');

      if (errors.length > 0) {
        toast.error(errors.join('\n'), { duration: 8000 });
      }

      if (allFunds.length === 0) {
        if (errors.length === 0) {
          toast.error('No transactions found in any PDF.', { duration: 5000 });
        }
        return;
      }

      setMfImportPreview({
        cas_id: casId,
        statement_period: statementPeriod,
        source: 'CDSL',
        funds: allFunds,
        summary: {
          total_purchases: totalPurchases,
          total_redemptions: totalRedemptions,
          funds_count: new Set(allFunds.map(f => f.fund_code)).size,
        },
        _fileCount: files.length,
      });
    } catch (err) {
      toast.dismiss('cdsl-cas-parse');
      const msg = err.response?.data?.detail || 'Failed to parse CDSL CAS statement';
      toast.error(msg, { duration: 5000 });
      throw err;
    }
  };

  const handleConfirmCDSLCASImport = async (funds) => {
    try {
      toast.loading('Importing MF transactions...', { id: 'cdsl-cas-import' });
      const result = await confirmCDSLCASImport({ funds });
      toast.dismiss('cdsl-cas-import');

      const parts = [];
      if (result.imported?.buys > 0) parts.push(`${result.imported.buys} buys`);
      if (result.imported?.sells > 0) parts.push(`${result.imported.sells} sells`);
      if (result.skipped_duplicates > 0) parts.push(`${result.skipped_duplicates} skipped`);
      toast.success(`CAS Import: ${parts.join(', ')}`, { duration: 5000 });

      if (result.errors?.length > 0) {
        toast.error(`${result.errors.length} error(s): ${result.errors[0]}`, { duration: 8000 });
      }

      setMfImportPreview(null);
      loadMutualFunds();
    } catch (err) {
      toast.dismiss('cdsl-cas-import');
      const msg = err.response?.data?.detail || 'Failed to import CAS transactions';
      toast.error(msg, { duration: 5000 });
    }
  };

  // ── Mutual Fund handlers ────────────────────────
  const handleAddMFHolding = async (data) => {
    try {
      await addMFHolding(data);
      toast.success(`Added ${data.units} units of ${data.fund_name}`);
      setAddMFModalData(null);
      loadMutualFunds();
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
      loadMutualFunds();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to redeem MF');
    }
  };

  const handleSaveSIP = async (config) => {
    try {
      await addSIPConfig(config);
      toast.success(`SIP configured for ${config.fund_name}`);
      setSipTarget(null);
      loadMutualFunds();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save SIP config');
    }
  };

  const handleDeleteSIP = async (fundCode) => {
    try {
      await deleteSIPConfig(fundCode);
      toast.success('SIP removed');
      setSipTarget(null);
      loadMutualFunds();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete SIP');
    }
  };

  const handleExecuteSIP = async (fundCode) => {
    try {
      const result = await executeSIP(fundCode);
      toast.success(result.message || 'SIP executed');
      loadMutualFunds();
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
      loadFD();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save FD');
    }
  };

  const handleDeleteFD = async (fdId) => {
    try {
      await deleteFD(fdId);
      toast.success('FD deleted');
      loadFD();
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
      loadRD();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save RD');
    }
  };

  const handleDeleteRD = async (rdId) => {
    try {
      await deleteRD(rdId);
      toast.success('RD deleted');
      loadRD();
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
      loadInsurance();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save policy');
    }
  };

  const handleDeleteInsurance = async (policyId) => {
    try {
      await deleteInsurance(policyId);
      toast.success('Policy deleted');
      loadInsurance();
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
        toast.success(data.new_sip_phase ? 'New SIP phase added' : 'PPF account updated');
      } else {
        await addPPF(data);
        toast.success(`Added PPF account: ${data.account_name}`);
      }
      setAddPPFModalData(null);
      loadPPF();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save PPF');
    }
  };

  const handleDeletePPF = async (ppfId) => {
    try {
      await deletePPF(ppfId);
      toast.success('PPF account deleted');
      loadPPF();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete PPF');
    }
  };

  const handleWithdrawPPF = async (ppfId, amount, date) => {
    try {
      await withdrawPPF(ppfId, { amount, date: date || new Date().toISOString().split('T')[0] });
      toast.success(`Withdrew ₹${Number(amount).toLocaleString('en-IN')} from PPF`);
      loadPPF();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to withdraw from PPF');
    }
  };

  // ── NPS handlers ────────────────────────────────
  const handleAddNPS = async (data) => {
    try {
      if (data.nps_id) {
        // Adding contribution
        await addNPSContribution(data.nps_id, { date: data.date, amount: data.amount, remarks: data.remarks });
        toast.success('Contribution added');
      } else if (data.id) {
        await updateNPS(data.id, data);
        toast.success('NPS account updated');
      } else {
        await addNPS(data);
        toast.success(`Added NPS account: ${data.account_name}`);
      }
      setAddNPSModalData(null);
      loadNPS();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save NPS');
    }
  };

  const handleDeleteNPS = async (npsId) => {
    try {
      await deleteNPS(npsId);
      toast.success('NPS account deleted');
      loadNPS();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete NPS');
    }
  };

  // ── Standing Instruction handlers ────────────────
  const handleAddSI = async (data) => {
    try {
      if (data.id) {
        await updateSI(data.id, data);
        toast.success('SI updated');
      } else {
        await addSI(data);
        toast.success(`Added SI: ${data.beneficiary} at ${data.bank}`);
      }
      setAddSIModalData(null);
      loadSI();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save SI');
    }
  };

  const handleDeleteSI = async (siId) => {
    try {
      await deleteSI(siId);
      toast.success('SI deleted');
      loadSI();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to delete SI');
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
          ) : activeTab === 'nps' ? (
            <button className="btn btn-primary" onClick={() => { setNpsModalMode('add'); setAddNPSModalData({}); }}>
              + Add NPS
            </button>
          ) : activeTab === 'standingInstructions' ? (
            <button className="btn btn-primary" onClick={() => setAddSIModalData({})}>
              + Add SI
            </button>
          ) : (
            <button className="btn btn-primary" onClick={() => setAddModalData({})}>
              + Add Stock
            </button>
          )}
        </div>
      </header>

      {/* Dashboard Summary — all asset classes */}
      <Dashboard summary={summary} mfDashboard={mfDashboard} fdDashboard={fdDashboard} rdDashboard={rdDashboard} ppfDashboard={ppfDashboard} npsDashboard={npsDashboard} loading={loading} />

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
        <button className={`tab ${activeTab === 'ppf' ? 'active' : ''}`} onClick={() => setActiveTab('ppf')}>
          PPF
        </button>
        <button className={`tab ${activeTab === 'nps' ? 'active' : ''}`} onClick={() => setActiveTab('nps')}>
          NPS
        </button>
        <button className={`tab ${activeTab === 'standingInstructions' ? 'active' : ''}`} onClick={() => setActiveTab('standingInstructions')}>
          Standing Instructions
        </button>
        <button className={`tab ${activeTab === 'insurance' ? 'active' : ''}`} onClick={() => setActiveTab('insurance')}>
          Insurance
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
          onImportCDSLCAS={handleParseCDSLCAS}
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
          onWithdrawPPF={handleWithdrawPPF}
          onRedeemPPF={(ppf) => {
            if (window.confirm(`Redeem PPF "${ppf.account_name}"?\nMaturity Value: ₹${Number(ppf.maturity_amount).toLocaleString('en-IN')}\n\nThis will delete the account.`)) {
              handleDeletePPF(ppf.id);
              toast.success(`PPF "${ppf.account_name}" redeemed successfully`);
            }
          }}
        />
      )}

      {activeTab === 'nps' && (
        <NPSTable
          accounts={npsAccounts}
          loading={loading}
          npsDashboard={npsDashboard}
          onAddNPS={() => { setNpsModalMode('add'); setAddNPSModalData({}); }}
          onEditNPS={(nps) => { setNpsModalMode('edit'); setAddNPSModalData(nps); }}
          onDeleteNPS={handleDeleteNPS}
          onAddContribution={(nps) => { setNpsModalMode('contribution'); setAddNPSModalData(nps); }}
        />
      )}

      {activeTab === 'standingInstructions' && (
        <StandingInstructionTable
          instructions={siSummary}
          loading={loading}
          siDashboard={siDashboard}
          onAddSI={() => setAddSIModalData({})}
          onEditSI={(si) => setAddSIModalData(si)}
          onDeleteSI={handleDeleteSI}
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

      {/* CDSL CAS Import Preview Modal */}
      {mfImportPreview && (
        <MFImportPreviewModal
          data={mfImportPreview}
          onConfirm={handleConfirmCDSLCASImport}
          onCancel={() => setMfImportPreview(null)}
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

      {/* NPS Modal (add / edit / contribution) */}
      {addNPSModalData !== null && (
        <AddNPSModal
          initialData={addNPSModalData}
          mode={npsModalMode}
          onSubmit={handleAddNPS}
          onClose={() => setAddNPSModalData(null)}
        />
      )}

      {/* SI Modal */}
      {addSIModalData !== null && (
        <AddSIModal
          initialData={addSIModalData}
          onAdd={handleAddSI}
          onClose={() => setAddSIModalData(null)}
        />
      )}
    </div>
  );
}
