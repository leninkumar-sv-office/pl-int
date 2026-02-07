================================================================================
STOCK PORTFOLIO DUPLICATE ANALYSIS - README
================================================================================

This analysis identifies 697 duplicate transaction rows across 45 stock files
in your portfolio dump directory.

================================================================================
ANALYSIS RESULTS SUMMARY
================================================================================

CRITICAL STATISTICS:
  - Total files analyzed: 67
  - Files with duplicates: 45 (67%)
  - Duplicate pairs found: 697
  - Rows affected: Multiple files with 20-101 duplicate pairs each

MOST CRITICAL FILES (>50 duplicates):
  1. Rallis India Ltd.xlsx                    101 duplicate pairs
  2. Rail Vikas Nigam.xlsx                     86 duplicate pairs
  3. High Energy Batteries (India) Ltd.xlsx    60 duplicate pairs
  4. Archive_Indian Railway Ctrng...           53 duplicate pairs
  5. Bombay Burmah Trading Corp Ltd.xlsx       52 duplicate pairs

================================================================================
DUPLICATE CHARACTERISTICS
================================================================================

Of the 697 duplicate pairs analyzed:

COST FIELD:
  - 25 pairs (3%) have empty COST in older row
  - 116 pairs (16%) have empty COST in newer row
  - 230 pairs (32%) have different COST values

EXCHANGE:
  - 46 pairs (6%) have different exchange (NSE vs BSE)

PRICE:
  - 352 pairs (50%) have identical prices
  - 345 pairs (50%) have prices within 5% tolerance

This pattern suggests:
  - Pre-migration manual entries (older rows, often missing COST)
  - Post-migration load file imports (newer rows, sometimes missing COST)
  - Data quality issues with cost calculations and exchange inconsistencies

================================================================================
HOW TO USE THE ANALYSIS
================================================================================

1. READ THE FULL REPORT:
   Open: DUPLICATE_ANALYSIS_REPORT.txt
   Contains: Methodology, detailed findings, recommendations

2. QUICK REFERENCE:
   Open: ANALYSIS_QUICK_REFERENCE.md
   Contains: Key metrics, top files, patterns, cleanup strategy

3. MACHINE-READABLE DATA:
   Open: duplicate_details.csv (in Excel or any CSV reader)
   Columns: Stock File, Row numbers, Dates, Actions, Prices, Costs, etc.
   Use for: Sorting, filtering, and detailed analysis

4. RUN ANALYSIS SCRIPTS:

   For detailed report with all duplicate pairs:
   $ python3 analyze_duplicates.py

   For summary report with top 10 files:
   $ python3 analyze_duplicates_summary.py

================================================================================
UNDERSTANDING THE DUPLICATE PAIRS
================================================================================

Each duplicate pair consists of two rows with:
  - Same DATE
  - Same ACTION (Buy or Sell)
  - Same QUANTITY
  - Similar PRICE (within 5%)

Example from Kajaria Ceramics Ltd.xlsx:
  Row 5:  2026-02-04 | Buy 1 @ 911.70 | Cost: 918.16 | NSE
  Row 6:  2026-02-04 | Buy 1 @ 911.70 | Cost: 918.16 | NSE
  → Exact duplicate - one should be removed

Example from Ashok Leyland Ltd.xlsx:
  Row 6:  2025-10-17 | Buy 50 @ 136.50 | Cost: 6873.28 | BSE
  Row 7:  2025-10-17 | Buy 50 @ 137.47 | Cost: None     | NSE
  → Same transaction, different exchange - needs review

Example from Rail Vikas Nigam.xlsx:
  Row 26: 2025-10-20 | Buy 40 @ 330.70 | Cost: 13321.59 | NSE
  Row 48: 2025-10-20 | Buy 40 @ 333.04 | Cost: None     | NSE
  → Similar transaction, missing cost in newer row

================================================================================
CLEANUP STRATEGY
================================================================================

BEFORE MAKING CHANGES:
  ✓ This analysis is READ-ONLY - no files have been modified
  ✓ Review the detailed findings in DUPLICATE_ANALYSIS_REPORT.txt
  ✓ Understand which rows are duplicates and why
  ✓ Make a BACKUP of your dump files

RECOMMENDED APPROACH:

  For EXACT DUPLICATES (identical rows):
    → Keep the older entry (pre-migration)
    → Remove the newer entry (post-migration)
    → Reason: Pre-migration data is likely from broker/manual entry

  For COST DIFFERENCES:
    → Compare with source load files
    → Keep the row with more complete cost calculation
    → If one row has empty COST, fill from the duplicate

  For EXCHANGE DIFFERENCES:
    → Verify which exchange the transaction actually occurred on
    → Keep the verified row
    → Investigate if it's a hedge transaction (same qty on diff exchange)

  For MISSING COSTS:
    → Fill missing COST values from the matching duplicate
    → If both missing, recalculate or research the transaction

PRIORITY ORDER:
  1. Files with 50+ duplicates (need careful review)
  2. Files with 20-50 duplicates (batch review)
  3. Files with <20 duplicates (standard cleanup)

================================================================================
OUTPUT FILES INCLUDED
================================================================================

1. analyze_duplicates.py
   - Python script for detailed duplicate analysis
   - Shows all 697 duplicate pairs with full details
   - Output: Console report (can be redirected to file)

2. analyze_duplicates_summary.py
   - Python script for summary analysis
   - Shows top 10 files with most duplicates
   - Cleaner output, easier to review

3. duplicate_details.csv
   - Machine-readable export of all duplicates
   - 697 rows of detailed duplicate information
   - Can be opened in Excel, Google Sheets, or any CSV viewer
   - Useful for sorting and filtering

4. DUPLICATE_ANALYSIS_REPORT.txt
   - Comprehensive analysis with methodology
   - Detailed findings and recommendations
   - Sample patterns and root cause analysis
   - Best for understanding the full scope of issues

5. ANALYSIS_QUICK_REFERENCE.md
   - Quick reference guide with key metrics
   - How to use the analysis files
   - Pattern examples and cleanup recommendations
   - Best for getting started quickly

6. README_ANALYSIS.txt
   - This file
   - Overview of all analysis files
   - Quick start guide

================================================================================
IMPORTANT NOTES
================================================================================

- This analysis is READ-ONLY: No files were modified
- All row numbers reference the actual Excel row index (including header)
- Price tolerance for matching: ±5%
- Only Buy/Sell transactions were analyzed (other transaction types skipped)
- Files skipped: Those starting with ~, ., or in _backup directories
- One file error: Vikas Lifecare Ltd.xlsx (missing 'Trading History' sheet)

================================================================================
NEXT STEPS
================================================================================

1. Review the analysis results:
   - Read DUPLICATE_ANALYSIS_REPORT.txt for full details
   - Check ANALYSIS_QUICK_REFERENCE.md for quick overview
   - Open duplicate_details.csv to see all duplicate pairs

2. Identify high-priority files:
   - Rallis India Ltd. (101 duplicates)
   - Rail Vikas Nigam (86 duplicates)
   - High Energy Batteries (60 duplicates)
   - Archive_Indian Railway (53 duplicates)
   - Bombay Burmah (52 duplicates)

3. Create a cleanup plan:
   - Determine which rows to keep/remove for each file
   - Plan how to handle cost field inconsistencies
   - Verify exchange discrepancies

4. Make a backup before cleaning:
   - Save original files to _backup directory
   - Implement cleanup based on your strategy
   - Validate results after cleanup

5. Implement prevention:
   - Add deduplication checks to migration process
   - Use composite keys for transaction uniqueness
   - Add data quality validation

================================================================================
QUESTIONS & SUPPORT
================================================================================

The analysis scripts are self-contained and can be re-run anytime:

  - To regenerate detailed report:
    $ python3 analyze_duplicates.py

  - To regenerate summary report:
    $ python3 analyze_duplicates_summary.py

All scripts are read-only and safe to run multiple times.

================================================================================
Generated: 2026-02-07
Analysis Status: COMPLETE - Ready for Review
================================================================================
