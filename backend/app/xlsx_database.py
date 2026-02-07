"""
XLSX-per-stock database layer.

Each stock is stored as an individual .xlsx file under dumps/Stocks/.
Holdings and sold positions are derived on-the-fly via FIFO matching
of Buy/Sell rows in each file's "Trading History" sheet.
"""

import hashlib
import json
import os
import threading
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import openpyxl
from openpyxl.styles import Font, PatternFill

from .models import Holding, SoldPosition, Transaction

# ═══════════════════════════════════════════════════════════
#  SYMBOL ↔ COMPANY-NAME MAP  (from existing dump filenames)
# ═══════════════════════════════════════════════════════════

SYMBOL_MAP: Dict[str, str] = {
    "ABB India Ltd": "ABB",
    "Afcons Infrastructure Ltd": "AFCONS",
    "Antony Waste Handling Cell Ltd": "ANTONYWASTE",
    "Apollo Hospitals Enterprise Ltd": "APOLLOHOSP",
    "Apollo Tyres Ltd": "APOLLOTYRE",
    "Ashok Leyland Ltd": "ASHOKLEY",
    "Asian Paints Ltd": "ASIANPAINT",
    "Aurobindo Pharma Ltd": "AUROPHARMA",
    "Aurum Proptech Ltd": "AURUMPROP",
    "Avanti Feeds": "AVANTIFEED",
    "Avanti Feeds Ltd - Archive": "AVANTIFEED",
    "Bharat Electronics Ltd": "BEL",
    "Bharat Wire Ropes Ltd": "BHARATWIRE",
    "Biocon Ltd": "BIOCON",
    "Bombay Burmah Trading Corporation Ltd": "BBTC",
    "Carysil Ltd": "CARYSIL",
    "Coal India Ltd": "COALINDIA",
    "Gautam Gems Ltd": "GAUTAMGEM",
    "Graphite India Ltd": "GRAPHITE",
    "Hero MotoCorp Ltd": "HEROMOTOCO",
    "High Energy Batteries (India) Ltd": "HIGHENERGY",
    "Hindustan Copper Ltd": "HINDCOPPER",
    "IRB Infra": "IRB",
    "ITC Hotels Ltd": "ITCHOTELS",
    "ITC Ltd": "ITC",
    "Indian Oil Corporation Ltd": "IOC",
    "Indian Rail Tour Corp Ltd": "IRCTC",
    "Indian Railway Fin Corp": "IRFC",
    "Indian Renewable Energy Dev Agency Ltd": "IREDA",
    "Ircon International Ltd": "IRCON",
    "Jio Financial Services Ltd": "JIOFIN",
    "Jio Financial Services Ltd(1)": "JIOFIN",
    "Kajaria Ceramics Ltd": "KAJARIACER",
    "LG Electronics India": "LGEELECTRO",
    "Larsen and Toubro Ltd": "LT",
    "Majesco Ltd": "MAJESCO",
    "Manuppuram Finance Ltd": "MANAPPURAM",
    "Nippon Silver": "NIPPONSILV",
    "ONGC": "ONGC",
    "Oil India Ltd": "OIL",
    "PI Industries Ltd": "PIIND",
    "PNC Infratech Ltd": "PNCINFRA",
    "Priti International Ltd": "PRITIINTER",
    "Rail Vikas Nigam": "RVNL",
    "Railtel Corporation of India Ltd": "RAILTEL",
    "Rallis India Ltd": "RALLIS",
    "Ramco Systems Ltd": "RAMCOSYS",
    "Reliance Industries Ltd": "RELIANCE",
    "Rites Ltd": "RITES",
    "SBI ETF Gold": "SETFGOLD",
    "SBI Life Insurance Company Ltd": "SBILIFE",
    "SBI": "SBIN",
    "Sun TV Network Ltd": "SUNTV",
    "Suzlon Energy": "SUZLON",
    "Syngene International Ltd": "SYNGENE",
    "TATA Capital": "TATACAPITAL",
    "TATA Power": "TATAPOWER",
    "Tata Chemicals": "TATACHEM",
    "Tata Motors Ltd": "TATAMOTORS",
    "Tata Steel Ltd": "TATASTEEL",
    "Tata Technologies Ltd": "TATATECH",
    "Trent": "TRENT",
    "Union Bank of India Ltd": "UNIONBANK",
    "Va Tech Wabag Ltd": "WABAG",
    "Vikas Lifecare Ltd": "VIKASLIFE",
    "Wipro Ltd": "WIPRO",
    "Archive_Indian Railway Ctrng nd Trsm Corp Ltd": "IRCTC",
}

# Reverse map: symbol → list of possible company names
_REVERSE_MAP: Dict[str, str] = {}
for _name, _sym in SYMBOL_MAP.items():
    if _sym not in _REVERSE_MAP:
        _REVERSE_MAP[_sym] = _name


# ═══════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════

def _gen_id(symbol: str, exchange: str, buy_date: str, buy_price: float, row_idx: int) -> str:
    """Deterministic holding ID from transaction data + row position."""
    key = f"{symbol}|{exchange}|{buy_date}|{buy_price:.4f}|{row_idx}"
    return hashlib.md5(key.encode()).hexdigest()[:8]


def _parse_date(val) -> Optional[str]:
    """Convert xlsx cell value to YYYY-MM-DD string."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _safe_float(val, default=0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val, default=0) -> int:
    if val is None:
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


# ═══════════════════════════════════════════════════════════
#  FIFO MATCHING  (extracted from import_dump.py)
# ═══════════════════════════════════════════════════════════

def fifo_match(buys: list, sells: list):
    """
    FIFO-match sells against buys.
    Returns (remaining_lots, sold_positions).
    Each lot in remaining_lots has a "remaining" key.
    """
    buys_sorted = sorted(buys, key=lambda x: x["date"])
    sells_sorted = sorted(sells, key=lambda x: x["date"])

    buy_lots = [{**b, "remaining": b["quantity"]} for b in buys_sorted]
    sold_positions = []

    for sell in sells_sorted:
        sell_qty = sell["quantity"]
        for lot in buy_lots:
            if sell_qty <= 0:
                break
            if lot["remaining"] <= 0:
                continue
            matched = min(lot["remaining"], sell_qty)
            realized_pl = (sell["price"] - lot["price"]) * matched
            sold_positions.append({
                "buy_price": lot["price"],
                "buy_date": lot["date"],
                "buy_exchange": lot.get("exchange", "NSE"),
                "sell_price": sell["price"],
                "sell_date": sell["date"],
                "quantity": matched,
                "realized_pl": round(realized_pl, 2),
                "row_idx": lot.get("row_idx", 0),
            })
            lot["remaining"] -= matched
            sell_qty -= matched

    remaining = [l for l in buy_lots if l["remaining"] > 0]
    return remaining, sold_positions


# ═══════════════════════════════════════════════════════════
#  XLSX PARSING
# ═══════════════════════════════════════════════════════════

def _extract_index_data(wb) -> dict:
    """Read metadata from the Index sheet."""
    data = {"code": None, "exchange": "NSE", "symbol": None,
            "current_price": 0, "week_52_high": 0, "week_52_low": 0}
    if "Index" not in wb.sheetnames:
        return data
    ws = wb["Index"]
    max_row = ws.max_row or 0
    if max_row == 0:
        return data
    for row in ws.iter_rows(min_row=1, max_row=min(15, max_row), values_only=False):
        vals = [c.value for c in row]
        if len(vals) >= 3:
            label = vals[1]
            value = vals[2]
            if label == "Code" and value:
                code = str(value)
                data["code"] = code
                if ":" in code:
                    parts = code.split(":")
                    data["exchange"] = parts[0]
                    data["symbol"] = parts[1]
            elif label == "Current Price" and isinstance(value, (int, float)):
                data["current_price"] = float(value)
            elif label == "52 Week High" and isinstance(value, (int, float)):
                data["week_52_high"] = float(value)
            elif label == "52 Week Low" and isinstance(value, (int, float)):
                data["week_52_low"] = float(value)
    return data


def _parse_excel_serial_date(val) -> Optional[str]:
    """Convert Excel serial date number to YYYY-MM-DD string."""
    if isinstance(val, (int, float)) and val > 1000:
        from datetime import timedelta
        base = datetime(1899, 12, 30)
        return (base + timedelta(days=int(val))).strftime("%Y-%m-%d")
    return _parse_date(val)


def _find_realised_columns(ws, header_row: int) -> dict:
    """Dynamically find the Realised section column positions.

    The "Realised" marker in row 2 tells us where the sold section starts.
    Under that marker, row 4 has sub-headers: Price, Date, [Gain%], Gain, Gross, Units.
    Column positions vary between file formats (new vs archive).
    """
    cols = {"sell_price": None, "sell_date": None, "sell_gain": None, "sold_units": None}

    # Step 1: Find "Realised" (but NOT "UnRealised") in row 2
    realised_col = None
    for c in range(10, ws.max_column + 1):
        val = ws.cell(2, c).value
        if val:
            val_str = str(val).strip()
            if val_str == "Realised" or val_str == "Realized":
                realised_col = c
                break

    if realised_col is None:
        return cols

    # Step 2: Read row 4 (header row) from the Realised column onward
    # and map sub-headers to column positions
    for c in range(realised_col, min(realised_col + 10, ws.max_column + 1)):
        header = ws.cell(header_row, c).value
        if not header:
            continue
        header = str(header).strip()

        if header == "Price" and cols["sell_price"] is None:
            cols["sell_price"] = c
        elif header == "Date" and cols["sell_date"] is None:
            cols["sell_date"] = c
        elif header == "Gain" and cols["sell_gain"] is None:
            cols["sell_gain"] = c
        elif header == "Units" and cols["sold_units"] is None:
            cols["sold_units"] = c

    return cols


def _parse_trading_history(wb) -> Tuple[list, list, list]:
    """Parse Buy and Sell rows from Trading History sheet using column layout.

    The xlsx format tracks sold lots directly in the Realised section:
      - Core: A=Date, B=Exch, C=Action, D=Qty, E=Price, F=Cost, ...
      - Realised section (position varies): Price, Date, Gain, Units

    Returns (held_lots, column_sold_lots, sell_rows):
      - held_lots: Buy rows WITHOUT Realised data (or partial remaining)
      - column_sold_lots: Buy rows WITH Realised data tracking sold lots
      - sell_rows: Explicit Sell action rows (for FIFO matching against held)
    """
    held, sold, sell_rows = [], [], []
    if "Trading History" not in wb.sheetnames:
        return held, sold, sell_rows
    ws = wb["Trading History"]
    max_row = ws.max_row or 0
    if max_row < 5:
        return held, sold, sell_rows

    # Find header row
    header_row = None
    for r in range(1, min(11, max_row + 1)):
        vals = [ws.cell(r, c).value for c in range(1, 5)]
        if "DATE" in vals and "ACTION" in vals:
            header_row = r
            break
    if header_row is None:
        return held, sold, sell_rows

    # Dynamically find the Realised section columns
    rcols = _find_realised_columns(ws, header_row)
    has_realised_section = rcols["sell_price"] is not None

    for row_idx in range(header_row + 1, max_row + 1):
        date_val = ws.cell(row_idx, 1).value        # A: DATE
        exch = ws.cell(row_idx, 2).value             # B: EXCH
        action = ws.cell(row_idx, 3).value           # C: ACTION
        qty = ws.cell(row_idx, 4).value              # D: QTY
        price = ws.cell(row_idx, 5).value            # E: PRICE

        if not action or not date_val:
            continue

        action = str(action).strip()
        exch = str(exch).strip() if exch else ""

        # Skip dividends
        if exch == "DIV":
            continue

        # Collect Sell rows for FIFO matching against held lots.
        # IMPORTANT: Original dump files have Sell rows alongside Realised
        # columns on Buy rows for the SAME sales — these would double-count.
        # So when a Realised section exists, only collect app-initiated sells
        # (marked with "APP_SELL" remark). When no Realised section exists,
        # collect all Sell rows (file was created by app or has no column data).
        if action == "Sell":
            remarks_val = str(ws.cell(row_idx, 7).value or "").strip()
            is_app_sell = remarks_val == "APP_SELL"
            if not has_realised_section or is_app_sell:
                tx_date = _parse_date(date_val)
                if not tx_date:
                    continue
                qty_int = _safe_int(qty)
                price_f = _safe_float(price)
                if qty_int > 0 and price_f > 0:
                    exchange = exch if exch in ("NSE", "BSE") else "NSE"
                    sell_rows.append({
                        "date": tx_date,
                        "quantity": qty_int,
                        "price": price_f,
                        "exchange": exchange,
                        "row_idx": row_idx,
                    })
            continue

        # Only process Buy rows
        if action != "Buy":
            continue

        tx_date = _parse_date(date_val)
        if not tx_date:
            continue

        qty_int = _safe_int(qty)
        price_f = _safe_float(price)
        if qty_int <= 0 or price_f <= 0:
            continue

        exchange = exch if exch in ("NSE", "BSE") else "NSE"

        # Check Realised section columns for sold data
        sell_price = 0.0
        sell_date_val = None
        sell_gain = 0.0
        sold_units = 0

        if has_realised_section:
            if rcols["sell_price"]:
                sell_price = _safe_float(ws.cell(row_idx, rcols["sell_price"]).value)
            if rcols["sell_date"]:
                sell_date_val = ws.cell(row_idx, rcols["sell_date"]).value
            if rcols["sell_gain"]:
                sell_gain = _safe_float(ws.cell(row_idx, rcols["sell_gain"]).value)
            if rcols["sold_units"]:
                sold_units = _safe_int(ws.cell(row_idx, rcols["sold_units"]).value)

        if sold_units > 0 and sell_price > 0:
            # This buy lot has been sold (fully or partially)
            sell_date = _parse_excel_serial_date(sell_date_val)
            if not sell_date:
                sell_date = tx_date  # fallback

            realized_pl = sell_gain if sell_gain != 0 else round((sell_price - price_f) * sold_units, 2)

            sold.append({
                "buy_date": tx_date,
                "buy_price": price_f,
                "sell_date": sell_date,
                "sell_price": sell_price,
                "quantity": sold_units,
                "realized_pl": round(realized_pl, 2),
                "exchange": exchange,
                "row_idx": row_idx,
            })

            # Check for partial sell (held = D - sold_units)
            held_qty = qty_int - sold_units
            if held_qty > 0:
                held.append({
                    "date": tx_date,
                    "exchange": exchange,
                    "quantity": held_qty,
                    "price": price_f,
                    "row_idx": row_idx,
                })
        else:
            # Not sold — entire lot is held
            held.append({
                "date": tx_date,
                "exchange": exchange,
                "quantity": qty_int,
                "price": price_f,
                "row_idx": row_idx,
            })

    return held, sold, sell_rows


# ═══════════════════════════════════════════════════════════
#  MAIN CLASS
# ═══════════════════════════════════════════════════════════

class XlsxPortfolio:
    """File-per-stock xlsx database with FIFO-derived holdings."""

    def __init__(self, stocks_dir: str | Path):
        self.stocks_dir = Path(stocks_dir)
        self.stocks_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Caches keyed by symbol (combined data from all files)
        self._cache: Dict[str, Tuple[float, List[Holding], List[SoldPosition]]] = {}
        # symbol → primary filepath (for writes)
        self._file_map: Dict[str, Path] = {}
        # symbol → ALL file paths (primary + archives, for reads)
        self._all_files: Dict[str, List[Path]] = {}
        # symbol → company name
        self._name_map: Dict[str, str] = {}
        # holding_id → Holding  (rebuilt on every full scan)
        self._holding_index: Dict[str, Holding] = {}
        # holding_id → filepath  (to find file for sell ops)
        self._holding_file: Dict[str, Path] = {}

        # Manual prices
        self._manual_prices_file = Path(stocks_dir).parent.parent / "backend" / "data" / "manual_prices.json"
        self._ensure_manual_prices()

        # Build file map on init
        self._build_file_map()

    # ── Initialisation ────────────────────────────────────

    def _ensure_manual_prices(self):
        self._manual_prices_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._manual_prices_file.exists():
            with open(self._manual_prices_file, "w") as f:
                json.dump({}, f)

    def _build_file_map(self):
        """Scan xlsx files and build symbol ↔ filepath map.

        Multiple files for the same symbol (main + archive + duplicates)
        are all stored so that transactions can be merged during parsing.
        The non-archive file is treated as the primary (for writes).
        """
        for fp in sorted(self.stocks_dir.glob("*.xlsx")):
            if fp.name.startswith("~") or fp.name.startswith("."):
                continue

            stem = fp.stem
            # Try SYMBOL_MAP first (fast, no xlsx open)
            symbol = SYMBOL_MAP.get(stem)
            if not symbol:
                clean = stem.replace("Archive_", "").replace(" - Archive", "").strip()
                symbol = SYMBOL_MAP.get(clean)

            if not symbol:
                # Try reading Index sheet
                try:
                    wb = openpyxl.load_workbook(fp, data_only=True)
                    idx = _extract_index_data(wb)
                    wb.close()
                    symbol = idx.get("symbol")
                except Exception:
                    pass

            if not symbol:
                symbol = stem.upper().replace(" LTD", "").replace(" ", "")[:12]

            # Skip "(1)" files — they are near-duplicates with rounding diffs
            if "(1)" in stem:
                continue

            # Accumulate all files for this symbol
            if symbol not in self._all_files:
                self._all_files[symbol] = []
            self._all_files[symbol].append(fp)

            # Primary file = non-archive (for writes)
            is_archive = "Archive" in stem
            existing = self._file_map.get(symbol)
            if existing is None or (not is_archive):
                self._file_map[symbol] = fp
                clean_name = stem.replace("Archive_", "").replace(" - Archive", "").strip()
                self._name_map[symbol] = clean_name

        print(f"[XlsxDB] Indexed {len(self._file_map)} stock files ({sum(len(v) for v in self._all_files.values())} total including archives)")

    def _find_file_for_symbol(self, symbol: str) -> Optional[Path]:
        """Find xlsx file for a given stock symbol."""
        symbol = symbol.upper()
        if symbol in self._file_map:
            return self._file_map[symbol]
        # Try glob fallback
        for fp in self.stocks_dir.glob("*.xlsx"):
            if symbol.lower() in fp.stem.lower():
                return fp
        return None

    # ── Cache Layer ───────────────────────────────────────

    def _get_stock_data(self, symbol: str) -> Tuple[List[Holding], List[SoldPosition]]:
        """Get holdings/sold for a symbol, combining all files, with mtime caching."""
        files = self._all_files.get(symbol, [])
        if not files:
            return [], []

        # Compute combined mtime (max of all files)
        try:
            combined_mtime = max(fp.stat().st_mtime for fp in files)
        except OSError:
            return [], []

        if symbol in self._cache:
            cached_mtime, cached_h, cached_s = self._cache[symbol]
            if cached_mtime == combined_mtime:
                return cached_h, cached_s

        holdings, sold = self._parse_and_match_symbol(symbol, files)
        self._cache[symbol] = (combined_mtime, holdings, sold)
        return holdings, sold

    def _invalidate_symbol(self, symbol: str):
        """Remove a symbol from cache so next read re-parses."""
        self._cache.pop(symbol, None)

    def _invalidate_all(self):
        """Clear all caches."""
        self._cache.clear()
        self._holding_index.clear()
        self._holding_file.clear()

    # ── Parse + FIFO ──────────────────────────────────────

    def _parse_and_match_symbol(self, symbol: str, files: List[Path]) -> Tuple[List[Holding], List[SoldPosition]]:
        """Parse ALL xlsx files for a symbol with hybrid sold detection.

        Column-based: Buy rows with Realised section data → sold via columns.
        FIFO-based: Explicit Sell rows are FIFO-matched against held lots.
        This ensures sells done through the app (which add Sell rows) are
        properly reflected alongside original column-tracked sells.
        """
        all_held, all_sold_raw, all_sell_rows = [], [], []
        exchange = "NSE"
        name = symbol

        for filepath in files:
            stem = filepath.stem
            try:
                wb = openpyxl.load_workbook(filepath, data_only=True)
            except Exception as e:
                print(f"[XlsxDB] Failed to open {filepath.name}: {e}")
                continue

            idx = _extract_index_data(wb)
            held, sold, sell_rows = _parse_trading_history(wb)
            wb.close()

            # Use index data from the primary (non-archive) file
            if idx.get("exchange"):
                exchange = idx["exchange"]
            clean_name = stem.replace("Archive_", "").replace(" - Archive", "").strip()
            if not name or name == symbol:
                name = clean_name

            all_held.extend(held)
            all_sold_raw.extend(sold)
            all_sell_rows.extend(sell_rows)

        if not all_held and not all_sold_raw and not all_sell_rows:
            return [], []

        # FIFO-match explicit Sell rows against held lots.
        # Column-tracked sells (Buy rows with Realised data) are already in
        # all_sold_raw and their lots are NOT in all_held, so no double-counting.
        if all_sell_rows and all_held:
            buys_for_fifo = [{
                "date": h["date"],
                "quantity": h["quantity"],
                "price": h["price"],
                "exchange": h.get("exchange", exchange),
                "row_idx": h.get("row_idx", 0),
            } for h in all_held]

            sells_for_fifo = [{
                "date": s["date"],
                "quantity": s["quantity"],
                "price": s["price"],
            } for s in all_sell_rows]

            remaining, fifo_sold = fifo_match(buys_for_fifo, sells_for_fifo)

            # Replace held lots with remaining after FIFO
            all_held = [{
                "date": r["date"],
                "exchange": r.get("exchange", exchange),
                "quantity": r["remaining"],
                "price": r["price"],
                "row_idx": r.get("row_idx", 0),
            } for r in remaining if r["remaining"] > 0]

            # Add FIFO-derived sold positions
            for fs in fifo_sold:
                all_sold_raw.append({
                    "buy_date": fs["buy_date"],
                    "buy_price": fs["buy_price"],
                    "sell_date": fs["sell_date"],
                    "sell_price": fs["sell_price"],
                    "quantity": fs["quantity"],
                    "realized_pl": fs["realized_pl"],
                    "exchange": fs.get("buy_exchange", exchange),
                    "row_idx": fs.get("row_idx", 0),
                })

        # Build Holding objects directly
        holdings = []
        for lot in all_held:
            h_id = _gen_id(symbol, lot.get("exchange", exchange),
                           lot["date"], lot["price"], lot.get("row_idx", 0))
            h = Holding(
                id=h_id,
                symbol=symbol,
                exchange=lot.get("exchange", exchange),
                name=name,
                quantity=lot["quantity"],
                buy_price=round(lot["price"], 2),
                buy_date=lot["date"],
                notes="",
            )
            holdings.append(h)

        # Build SoldPosition objects directly
        sold = []
        for s in all_sold_raw:
            s_id = _gen_id(symbol + "_S", s.get("exchange", exchange),
                           s["sell_date"], s["sell_price"], s.get("row_idx", 0))
            sold.append(SoldPosition(
                id=s_id,
                symbol=symbol,
                exchange=s.get("exchange", exchange),
                name=name,
                quantity=s["quantity"],
                buy_price=round(s["buy_price"], 2),
                buy_date=s["buy_date"],
                sell_price=round(s["sell_price"], 2),
                sell_date=s["sell_date"],
                realized_pl=s["realized_pl"],
            ))

        return holdings, sold

    # ── Public READ API ───────────────────────────────────

    def get_all_holdings(self) -> List[Holding]:
        """Get all current holdings across every stock file."""
        all_holdings: List[Holding] = []
        self._holding_index.clear()
        self._holding_file.clear()

        for symbol in self._file_map:
            holdings, _ = self._get_stock_data(symbol)
            primary_fp = self._file_map[symbol]
            for h in holdings:
                self._holding_index[h.id] = h
                self._holding_file[h.id] = primary_fp
            all_holdings.extend(holdings)

        return all_holdings

    def get_holding_by_id(self, holding_id: str) -> Optional[Holding]:
        """Lookup a specific holding by its deterministic ID."""
        # Try index first (populated by get_all_holdings)
        if holding_id in self._holding_index:
            return self._holding_index[holding_id]
        # Fallback: full scan
        self.get_all_holdings()
        return self._holding_index.get(holding_id)

    def get_all_sold(self) -> List[SoldPosition]:
        """Get all sold positions (FIFO-derived) across every stock file."""
        all_sold: List[SoldPosition] = []
        for symbol in self._file_map:
            _, sold = self._get_stock_data(symbol)
            all_sold.extend(sold)
        return all_sold

    # ── Public WRITE API ──────────────────────────────────

    def add_holding(self, holding: Holding) -> Holding:
        """Add a Buy transaction to the stock's xlsx file."""
        symbol = holding.symbol.upper()
        exchange = holding.exchange.upper()
        name = holding.name or symbol

        filepath = self._find_file_for_symbol(symbol)
        if filepath is None:
            filepath = self._create_stock_file(symbol, exchange, name)

        tx = Transaction(
            date=holding.buy_date,
            exchange=exchange,
            action="Buy",
            quantity=holding.quantity,
            price=holding.buy_price,
            remarks=holding.notes or "~",
        )
        self._insert_transaction(filepath, tx)
        self._invalidate_symbol(symbol)

        # Re-parse to get the proper deterministic ID
        holdings, _ = self._get_stock_data(symbol)
        # Find the one we just added (most recent buy matching date+price+qty)
        for h in holdings:
            if (h.buy_date == holding.buy_date and
                    abs(h.buy_price - holding.buy_price) < 0.01 and
                    h.quantity == holding.quantity):
                return h

        # Fallback
        holding.id = _gen_id(symbol, exchange, holding.buy_date, holding.buy_price, 5)
        return holding

    def add_sell_transaction(self, symbol: str, exchange: str,
                             quantity: int, price: float, sell_date: str):
        """Insert a Sell row into the stock's xlsx file.

        Marks the row with 'APP_SELL' so the parser knows to FIFO-match it
        against held lots (as opposed to original Sell rows that are already
        tracked via Realised columns on Buy rows).
        """
        symbol = symbol.upper()
        filepath = self._find_file_for_symbol(symbol)
        if filepath is None:
            raise FileNotFoundError(f"No xlsx file for symbol {symbol}")

        tx = Transaction(
            date=sell_date,
            exchange=exchange,
            action="Sell",
            quantity=quantity,
            price=price,
            remarks="APP_SELL",
        )
        self._insert_transaction(filepath, tx)
        self._invalidate_symbol(symbol)

    def remove_holding(self, holding_id: str) -> bool:
        """
        Remove a holding by deleting its Buy row from the xlsx.
        Use sparingly — selling is the normal workflow.
        """
        holding = self.get_holding_by_id(holding_id)
        if not holding:
            return False

        filepath = self._holding_file.get(holding_id)
        if not filepath:
            return False

        try:
            wb = openpyxl.load_workbook(filepath)
            ws = wb["Trading History"]
            # Find the row
            header_row = self._find_header_row(ws)
            for row_idx in range(header_row + 1, ws.max_row + 1):
                tx_date = _parse_date(ws.cell(row_idx, 1).value)
                action = ws.cell(row_idx, 3).value
                price = _safe_float(ws.cell(row_idx, 5).value)
                if (action == "Buy" and tx_date == holding.buy_date and
                        abs(price - holding.buy_price) < 0.01):
                    ws.delete_rows(row_idx)
                    wb.save(filepath)
                    # Find symbol for this file to invalidate cache
                    for sym, fp in self._file_map.items():
                        if fp == filepath:
                            self._invalidate_symbol(sym)
                            break
                    return True
            wb.close()
        except Exception as e:
            print(f"[XlsxDB] Failed to remove holding: {e}")
        return False

    # ── XLSX Write Helpers ────────────────────────────────

    def _find_header_row(self, ws) -> int:
        """Find the header row in a Trading History sheet."""
        for r in range(1, 11):
            vals = [ws.cell(r, c).value for c in range(1, 5)]
            if "DATE" in vals and "ACTION" in vals:
                return r
        return 4  # default

    def _insert_transaction(self, filepath: Path, tx: Transaction):
        """Insert a transaction row at the top of Trading History."""
        with self._lock:
            wb = openpyxl.load_workbook(filepath)
            ws = wb["Trading History"]
            header_row = self._find_header_row(ws)
            insert_at = header_row + 1  # row 5 by default

            ws.insert_rows(insert_at)

            # A: DATE
            try:
                dt = datetime.strptime(tx.date, "%Y-%m-%d")
            except ValueError:
                dt = datetime.now()
            ws.cell(insert_at, 1, value=dt)

            # B: EXCH
            ws.cell(insert_at, 2, value=tx.exchange)
            # C: ACTION
            ws.cell(insert_at, 3, value=tx.action)
            # D: QTY
            ws.cell(insert_at, 4, value=tx.quantity)
            # E: PRICE
            ws.cell(insert_at, 5, value=tx.price)
            # F: COST
            ws.cell(insert_at, 6, value=round(tx.price * tx.quantity, 2))
            # G: REMARKS
            ws.cell(insert_at, 7, value=tx.remarks or "~")
            # H: STT
            if tx.stt:
                ws.cell(insert_at, 8, value=tx.stt)
            # I: ADD CHRG
            if tx.add_chrg:
                ws.cell(insert_at, 9, value=tx.add_chrg)

            # J: Current Price formula (only for Buy rows)
            if tx.action == "Buy":
                ws.cell(insert_at, 10, value="=Index!$C$2")

            wb.save(filepath)

    def _create_stock_file(self, symbol: str, exchange: str, company_name: str) -> Path:
        """Create a new xlsx file with proper template structure."""
        filename = f"{company_name}.xlsx"
        filepath = self.stocks_dir / filename

        wb = openpyxl.Workbook()

        # ── Trading History sheet ─────────────────────────
        ws = wb.active
        ws.title = "Trading History"

        headers = [
            "DATE", "EXCH", "ACTION", "QTY", "PRICE", "COST",
            "REMARKS", "STT", "ADD CHRG", "Current Price",
            "Gain %", "Gain", "Gross", "Units",
        ]
        header_font = Font(bold=True)
        header_fill = PatternFill("solid", fgColor="FF967BB6")

        for col, h in enumerate(headers, 1):
            cell = ws.cell(4, col, value=h)
            cell.font = header_font
            cell.fill = header_fill

        # Sub-headers (rows 2-3) to match existing format
        ws.cell(2, 10, value="UnRealised")
        ws.cell(3, 10, value="Total")

        # Column widths
        widths = {1: 12, 2: 6, 3: 6, 4: 6, 5: 10, 6: 12,
                  7: 10, 8: 8, 9: 8, 10: 12, 11: 10, 12: 12, 13: 12, 14: 8}
        for col, w in widths.items():
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = w

        # ── Index sheet ───────────────────────────────────
        ws_idx = wb.create_sheet("Index")
        ws_idx.cell(1, 2, value="Code")
        ws_idx.cell(1, 3, value=f"{exchange}:{symbol}")
        ws_idx.cell(2, 2, value="Current Price")
        ws_idx.cell(2, 3, value=0)
        ws_idx.cell(2, 5, value="Commission")
        ws_idx.cell(2, 6, value=0.007)
        ws_idx.cell(3, 2, value="52 Week High")
        ws_idx.cell(3, 3, value=0)
        ws_idx.cell(4, 2, value="52 Week Low")
        ws_idx.cell(4, 3, value=0)
        ws_idx.cell(6, 2, value="UnRealised")
        ws_idx.cell(8, 1, value="All")
        ws_idx.cell(8, 2, value="Units")
        ws_idx.cell(8, 3, value=0)
        ws_idx.cell(11, 2, value="Invested")
        ws_idx.cell(11, 3, value=0)

        wb.save(filepath)

        # Register in maps
        self._file_map[symbol] = filepath
        self._name_map[symbol] = company_name

        print(f"[XlsxDB] Created new stock file: {filename}")
        return filepath

    # ── Manual Prices ─────────────────────────────────────

    def get_manual_price(self, symbol: str, exchange: str) -> Optional[float]:
        try:
            with open(self._manual_prices_file) as f:
                prices = json.load(f)
            return prices.get(f"{symbol}.{exchange}")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def set_manual_price(self, symbol: str, exchange: str, price: float):
        try:
            with open(self._manual_prices_file) as f:
                prices = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            prices = {}
        prices[f"{symbol}.{exchange}"] = price
        with open(self._manual_prices_file, "w") as f:
            json.dump(prices, f, indent=2)

    def get_all_manual_prices(self) -> dict:
        try:
            with open(self._manual_prices_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


# ═══════════════════════════════════════════════════════════
#  MODULE-LEVEL SINGLETON
# ═══════════════════════════════════════════════════════════

# Path: relative to backend/ directory → ../dumps/Stocks
_STOCKS_DIR = Path(__file__).parent.parent.parent / "dumps" / "Stocks"

xlsx_db = XlsxPortfolio(_STOCKS_DIR)
