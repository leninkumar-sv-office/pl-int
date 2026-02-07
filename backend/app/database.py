"""
File-system based JSON database for portfolio management.
"""
import json
import os
from typing import List, Optional
from .models import Holding, SoldPosition

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_FILE = os.path.join(DATA_DIR, "portfolio.json")


def _ensure_db():
    """Ensure the database file exists with proper structure."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DB_FILE):
        _write_db({"holdings": [], "sold": [], "manual_prices": {}})


def _read_db() -> dict:
    """Read the entire database."""
    _ensure_db()
    with open(DB_FILE, "r") as f:
        data = json.load(f)
    # Ensure all keys exist
    data.setdefault("holdings", [])
    data.setdefault("sold", [])
    data.setdefault("manual_prices", {})
    return data


def _write_db(data: dict):
    """Write the entire database."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Holdings ──────────────────────────────────────────────

def get_all_holdings() -> List[Holding]:
    """Get all current holdings."""
    db = _read_db()
    return [Holding(**h) for h in db["holdings"]]


def get_holding_by_id(holding_id: str) -> Optional[Holding]:
    """Get a specific holding by ID."""
    db = _read_db()
    for h in db["holdings"]:
        if h["id"] == holding_id:
            return Holding(**h)
    return None


def add_holding(holding: Holding) -> Holding:
    """Add a new holding to the portfolio."""
    db = _read_db()
    db["holdings"].append(holding.model_dump())
    _write_db(db)
    return holding


def update_holding(holding_id: str, quantity: int) -> Optional[Holding]:
    """Update quantity of an existing holding."""
    db = _read_db()
    for i, h in enumerate(db["holdings"]):
        if h["id"] == holding_id:
            if quantity <= 0:
                # Remove holding entirely
                db["holdings"].pop(i)
                _write_db(db)
                return None
            else:
                db["holdings"][i]["quantity"] = quantity
                _write_db(db)
                return Holding(**db["holdings"][i])
    return None


def remove_holding(holding_id: str) -> bool:
    """Remove a holding entirely."""
    db = _read_db()
    original_len = len(db["holdings"])
    db["holdings"] = [h for h in db["holdings"] if h["id"] != holding_id]
    if len(db["holdings"]) < original_len:
        _write_db(db)
        return True
    return False


# ── Sold Positions ────────────────────────────────────────

def get_all_sold() -> List[SoldPosition]:
    """Get all sold positions."""
    db = _read_db()
    return [SoldPosition(**s) for s in db["sold"]]


def add_sold_position(sold: SoldPosition) -> SoldPosition:
    """Record a sold position."""
    db = _read_db()
    db["sold"].append(sold.model_dump())
    _write_db(db)
    return sold


# ── Manual Prices ─────────────────────────────────────────

def get_manual_price(symbol: str, exchange: str) -> Optional[float]:
    """Get manually set price for a stock."""
    db = _read_db()
    key = f"{symbol}.{exchange}"
    return db["manual_prices"].get(key)


def set_manual_price(symbol: str, exchange: str, price: float):
    """Set a manual price for a stock."""
    db = _read_db()
    key = f"{symbol}.{exchange}"
    db["manual_prices"][key] = price
    _write_db(db)


def get_all_manual_prices() -> dict:
    """Get all manual prices."""
    db = _read_db()
    return db.get("manual_prices", {})
