---
name: import-data
description: Run CDSL CAS import from Gmail with proper dedup handling. Use when user asks to import portfolio data, refresh holdings, or sync from Gmail.
user_invocable: true
---

# Import Portfolio Data

Run the CDSL CAS import pipeline to refresh mutual fund holdings from Gmail CAS PDFs.

## Steps

### 1. Check for new CAS PDFs

```bash
cd /Users/lenin/Desktop/workspace/pl/backend
ls -lt data/cas_pdfs/*.pdf 2>/dev/null | head -10
```

Report how many PDFs are available and the most recent one.

### 2. Run the import

```bash
cd /Users/lenin/Desktop/workspace/pl/backend
python import_cdsl_cas_from_gmail.py
```

Key behaviors:
- Uses `skip_dup_check=True` — CAS-level dedup handles duplicates
- Parses ALL CAS PDFs, collects transactions per ISIN
- De-duplicates at transaction level (same date + units + NAV + action)
- Seeds opening balances from earliest CAS for pre-2019 funds
- Verifies against latest CAS closing balances

### 3. Post-import verification

After import completes:
1. Check the output for any verification failures or warnings
2. Report the number of funds imported and any discrepancies
3. If there were errors, show them clearly and suggest fixes

### 4. Sync to Drive (if needed)

If the user wants to sync the updated data to Google Drive:
```bash
cd /Users/lenin/Desktop/workspace/pl/backend
python -c "from app.drive_service import sync_up; sync_up()"
```
