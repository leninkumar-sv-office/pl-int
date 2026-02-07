# Stock Portfolio Duplicate Analysis - Quick Reference

## Key Findings

| Metric | Value |
|--------|-------|
| Total Files Analyzed | 67 |
| Files with Duplicates | 45 (67%) |
| **Total Duplicate Pairs** | **697** |
| Avg duplicates per file | 15.5 pairs |

## Top 5 Most Affected Files

1. **Rallis India Ltd.xlsx** - 101 duplicate pairs (181 total rows)
2. **Rail Vikas Nigam.xlsx** - 86 duplicate pairs (47 total rows)
3. **High Energy Batteries Ltd.xlsx** - 60 duplicate pairs (48 total rows)
4. **Archive_Indian Railway Corp.xlsx** - 53 duplicate pairs (89 total rows)
5. **Bombay Burmah Trading Corp Ltd.xlsx** - 52 duplicate pairs (122 total rows)

## Duplicate Characteristics

### Cost Field Issues
- Cost empty in older row: 25 pairs (3%)
- Cost empty in newer row: 116 pairs (16%)
- Cost values differ: 230 pairs (32%)

### Exchange Differences
- Exchange differs: 46 pairs (6%)
  - Indicates same transaction on different exchange (NSE vs BSE)

### Price Patterns
- Prices identical: 352 pairs (50%)
- Prices within 5%: 345 pairs (50%)

## Detection Algorithm

**Fuzzy Key Matching:**
1. Same DATE + ACTION (BUY/SELL) + QUANTITY
2. Plus: Price values within 5% tolerance

This captures transactions entered twice but with minor variations.

## Output Files

| File | Purpose | Format |
|------|---------|--------|
| `analyze_duplicates.py` | Detailed report script | Python |
| `analyze_duplicates_summary.py` | Summary report script | Python |
| `duplicate_details.csv` | Machine-readable export | CSV |
| `DUPLICATE_ANALYSIS_REPORT.txt` | Full analysis report | Text |

## How to Use

### Run the detailed analysis:
```bash
python3 analyze_duplicates.py > detailed_report.txt
```

### Run the summary analysis:
```bash
python3 analyze_duplicates_summary.py
```

### Review duplicates in Excel:
```bash
# Open the CSV in your spreadsheet application
open duplicate_details.csv
```

## Pattern Examples

### Pattern 1: Exact Duplicates
```
Row 5:  2026-02-04 | Buy 1 @ 911.70 | Cost: 918.16 | NSE
Row 6:  2026-02-04 | Buy 1 @ 911.70 | Cost: 918.16 | NSE
→ Exact same row, likely migration error
```

### Pattern 2: Different Exchange
```
Row 6:  2025-10-17 | Buy 50 @ 136.50 | Cost: 6873.28 | BSE
Row 7:  2025-10-17 | Buy 50 @ 137.47 | Cost: None     | NSE
→ Same transaction on different exchange
```

### Pattern 3: Missing Cost
```
Row 26: 2025-10-20 | Buy 40 @ 330.70 | Cost: 13321.59 | NSE
Row 48: 2025-10-20 | Buy 40 @ 333.04 | Cost: None     | NSE
→ Newer row missing cost calculation
```

## Cleanup Recommendations

### Priority 1: Files with 50+ duplicates
- Manual review required for accuracy
- Estimated 253 duplicate pairs across 5 files

### Priority 2: Files with 20-50 duplicates
- Review for data consistency
- Estimated 172 duplicate pairs across 5 files

### Priority 3: Files with <20 duplicates
- Batch review and cleanup
- Estimated 272 duplicate pairs across 35 files

## Root Cause Analysis

The duplicates likely originated from:

1. **Pre-migration entries** (manually entered)
   - Often have empty COST field
   - Created before migration script ran
   - Row position suggests: earlier rows

2. **Post-migration imports** (from load files)
   - Sometimes have empty COST field
   - Created by migration script
   - Row position suggests: later rows

3. **Data quality issues**
   - Exchange discrepancies (6% of pairs)
   - Cost calculation differences (32% of pairs)
   - Price rounding variations

## Next Steps

1. ✓ **Analysis Complete** - 697 duplicate pairs identified
2. **Manual Review** - Determine which row is authoritative
3. **Data Reconciliation** - Merge best data from both rows
4. **Cleanup** - Remove duplicates per cleanup strategy
5. **Prevention** - Implement deduplication checks

## Column Mapping Reference

| Column | Name | Load File | Notes |
|--------|------|-----------|-------|
| A | DATE | B (DATE) | Transaction date |
| B | EXCH | C (EXCHANGE) | NSE or BSE |
| C | ACTION | D (ACTION) | Buy or Sell |
| D | QTY | F (QTY) | Number of shares |
| E | PRICE | G (TRANSACTION PRICE) | Per share price |
| F | COST | H (VALUE AT COST) | Total transaction cost |
| G | REMARKS | - | Additional notes |
| H | STT | - | Securities Transaction Tax |
| I | ADD CHRG | - | Additional charges |

## Statistics by Category

### Files by Duplicate Count Range

| Range | Count | Files |
|-------|-------|-------|
| 50+ | 5 | Rallis, Rail Vikas, HEB, Archive Railway, Bombay Burmah |
| 20-49 | 5 | Wire Ropes, Ashok Leyland, Antony Waste, Kajaria, Ramco |
| 1-19 | 35 | Various |
| 0 (Clean) | 22 | Various |

### Duplicate Pair Characteristics

| Characteristic | Count | % |
|---|---|---|
| Cost empty (older) | 25 | 3% |
| Cost empty (newer) | 116 | 16% |
| Cost differs | 230 | 32% |
| Exchange differs | 46 | 6% |
| Price identical | 352 | 50% |

---

**Generated:** 2026-02-07  
**Analysis Type:** Read-Only (No files modified)  
**No action taken without explicit review**
