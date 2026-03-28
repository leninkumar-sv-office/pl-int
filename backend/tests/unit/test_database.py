"""Unit tests for app/database.py — Legacy stock portfolio JSON database."""
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.models import Holding, SoldPosition


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_dir(tmp_path):
    """Create temp data dir and patch database module to use it."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_file = str(data_dir / "portfolio.json")

    with patch("app.database.DATA_DIR", str(data_dir)), \
         patch("app.database.DB_FILE", db_file), \
         patch("app.database._write_db", wraps=_write_db_no_sync(db_file)):
        yield data_dir


def _write_db_no_sync(db_file):
    """Replacement _write_db that skips drive sync."""
    def _write(data: dict):
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        with open(db_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
    return _write


# ---------------------------------------------------------------------------
# Tests — ensure_db / empty state
# ---------------------------------------------------------------------------

def test_ensure_db_creates_file(db_dir):
    from app.database import _ensure_db, _read_db
    _ensure_db()
    db = _read_db()
    assert "holdings" in db
    assert "sold" in db
    assert "manual_prices" in db


def test_get_all_holdings_empty(db_dir):
    from app.database import get_all_holdings
    holdings = get_all_holdings()
    assert holdings == []


def test_get_all_sold_empty(db_dir):
    from app.database import get_all_sold
    sold = get_all_sold()
    assert sold == []


# ---------------------------------------------------------------------------
# Tests — add holding
# ---------------------------------------------------------------------------

def test_add_holding(db_dir):
    from app.database import add_holding, get_all_holdings
    h = Holding(
        symbol="RELIANCE",
        exchange="NSE",
        name="Reliance Industries",
        quantity=10,
        price=2500.0,
        buy_price=2500.0,
        buy_cost=25000.0,
        buy_date="2024-01-15",
    )
    result = add_holding(h)
    assert result.symbol == "RELIANCE"

    holdings = get_all_holdings()
    assert len(holdings) == 1
    assert holdings[0].symbol == "RELIANCE"
    assert holdings[0].quantity == 10


def test_add_multiple_holdings(db_dir):
    from app.database import add_holding, get_all_holdings
    for sym in ["TCS", "INFY", "HDFCBANK"]:
        add_holding(Holding(
            symbol=sym,
            exchange="NSE",
            name=sym,
            quantity=5,
            price=100.0,
            buy_price=100.0,
            buy_date="2024-01-01",
        ))
    holdings = get_all_holdings()
    assert len(holdings) == 3


# ---------------------------------------------------------------------------
# Tests — get_holding_by_id
# ---------------------------------------------------------------------------

def test_get_holding_by_id(db_dir):
    from app.database import add_holding, get_holding_by_id
    h = Holding(
        id="test123",
        symbol="WIPRO",
        exchange="NSE",
        name="Wipro",
        quantity=20,
        price=400.0,
        buy_price=400.0,
        buy_date="2024-03-01",
    )
    add_holding(h)
    found = get_holding_by_id("test123")
    assert found is not None
    assert found.symbol == "WIPRO"


def test_get_holding_by_id_not_found(db_dir):
    from app.database import get_holding_by_id
    assert get_holding_by_id("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests — update holding
# ---------------------------------------------------------------------------

def test_update_holding_quantity(db_dir):
    from app.database import add_holding, update_holding, get_all_holdings
    h = Holding(
        id="upd001",
        symbol="SBIN",
        exchange="NSE",
        name="SBI",
        quantity=10,
        price=600.0,
        buy_price=600.0,
        buy_date="2024-02-01",
    )
    add_holding(h)

    updated = update_holding("upd001", 25)
    assert updated is not None
    assert updated.quantity == 25

    holdings = get_all_holdings()
    assert holdings[0].quantity == 25


def test_update_holding_to_zero_removes(db_dir):
    from app.database import add_holding, update_holding, get_all_holdings
    h = Holding(
        id="upd002",
        symbol="ITC",
        exchange="NSE",
        name="ITC",
        quantity=5,
        price=450.0,
        buy_price=450.0,
        buy_date="2024-04-01",
    )
    add_holding(h)

    result = update_holding("upd002", 0)
    assert result is None

    holdings = get_all_holdings()
    assert len(holdings) == 0


def test_update_nonexistent_returns_none(db_dir):
    from app.database import update_holding
    result = update_holding("nope", 10)
    assert result is None


# ---------------------------------------------------------------------------
# Tests — remove holding
# ---------------------------------------------------------------------------

def test_remove_holding(db_dir):
    from app.database import add_holding, remove_holding, get_all_holdings
    h = Holding(
        id="rem001",
        symbol="TATAMOTORS",
        exchange="NSE",
        name="Tata Motors",
        quantity=15,
        price=800.0,
        buy_price=800.0,
        buy_date="2024-05-01",
    )
    add_holding(h)
    assert remove_holding("rem001") is True
    assert get_all_holdings() == []


def test_remove_nonexistent_returns_false(db_dir):
    from app.database import remove_holding
    assert remove_holding("nope") is False


# ---------------------------------------------------------------------------
# Tests — sold positions
# ---------------------------------------------------------------------------

def test_add_sold_position(db_dir):
    from app.database import add_sold_position, get_all_sold
    s = SoldPosition(
        symbol="RELIANCE",
        exchange="NSE",
        name="Reliance",
        quantity=5,
        buy_price=2500.0,
        buy_date="2024-01-15",
        sell_price=2800.0,
        sell_date="2024-06-15",
        realized_pl=1500.0,
    )
    result = add_sold_position(s)
    assert result.realized_pl == 1500.0

    sold = get_all_sold()
    assert len(sold) == 1
    assert sold[0].symbol == "RELIANCE"


# ---------------------------------------------------------------------------
# Tests — manual prices
# ---------------------------------------------------------------------------

def test_set_and_get_manual_price(db_dir):
    from app.database import set_manual_price, get_manual_price
    set_manual_price("UNLISTED", "NSE", 99.50)
    assert get_manual_price("UNLISTED", "NSE") == 99.50


def test_get_manual_price_not_set(db_dir):
    from app.database import get_manual_price
    assert get_manual_price("NOPE", "NSE") is None


def test_get_all_manual_prices(db_dir):
    from app.database import set_manual_price, get_all_manual_prices
    set_manual_price("A", "NSE", 10.0)
    set_manual_price("B", "BSE", 20.0)
    prices = get_all_manual_prices()
    assert prices["A.NSE"] == 10.0
    assert prices["B.BSE"] == 20.0


# ---------------------------------------------------------------------------
# Tests — _write_db (direct call, covers lines 34-36)
# ---------------------------------------------------------------------------

def test_write_db_creates_data_dir_and_file(tmp_path):
    """Directly call _write_db to cover its os.makedirs + json.dump."""
    from app import database as db
    data_dir = str(tmp_path / "newdata")
    db_file = str(tmp_path / "newdata" / "portfolio.json")
    with patch("app.database.DATA_DIR", data_dir), \
         patch("app.database.DB_FILE", db_file):
        db._write_db({"holdings": [], "sold": [], "manual_prices": {}})
    assert Path(db_file).exists()
    data = json.loads(Path(db_file).read_text())
    assert data["holdings"] == []
