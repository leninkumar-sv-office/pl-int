"""Integration tests for stock portfolio endpoints."""

import pytest

HEADERS = {"X-User-Id": "testuser"}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _add_stock(client, symbol="RELIANCE", qty=10, price=2500.0, exchange="NSE"):
    return client.post(
        "/api/portfolio/add",
        json={
            "symbol": symbol,
            "exchange": exchange,
            "name": f"{symbol} Industries",
            "quantity": qty,
            "buy_price": price,
            "buy_date": "2024-01-15",
        },
        headers=HEADERS,
    )


# ── GET /api/portfolio ───────────────────────────────────────────────────────

def test_get_portfolio_returns_list(app_client):
    """GET /api/portfolio returns 200 with a list."""
    response = app_client.get("/api/portfolio", headers=HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ── POST /api/portfolio/add ──────────────────────────────────────────────────

def test_add_stock_returns_200(app_client):
    """POST /api/portfolio/add returns 200 with holding data."""
    response = _add_stock(app_client)
    assert response.status_code == 200


def test_add_stock_response_shape(app_client):
    """Added stock has required fields in response."""
    response = _add_stock(app_client)
    data = response.json()
    assert "id" in data
    assert data["symbol"] == "RELIANCE"
    assert data["quantity"] == 10
    assert data["buy_price"] == 2500.0


def test_add_stock_missing_symbol_returns_422(app_client):
    """POST /api/portfolio/add without symbol returns 422."""
    response = app_client.post(
        "/api/portfolio/add",
        json={"quantity": 10, "buy_price": 100.0, "buy_date": "2024-01-15"},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_add_stock_missing_quantity_uses_default(app_client):
    """POST /api/portfolio/add without quantity succeeds with default 0."""
    response = app_client.post(
        "/api/portfolio/add",
        json={"symbol": "TCS", "buy_price": 100.0, "buy_date": "2024-01-15"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 0


def test_add_stock_missing_buy_price_uses_default(app_client):
    """POST /api/portfolio/add without buy_price succeeds with default 0."""
    response = app_client.post(
        "/api/portfolio/add",
        json={"symbol": "TCS", "quantity": 5, "buy_date": "2024-01-15"},
        headers=HEADERS,
    )
    assert response.status_code == 200
    assert response.json()["buy_price"] == 0


def test_add_stock_missing_buy_date_uses_default(app_client):
    """POST /api/portfolio/add without buy_date succeeds with default."""
    response = app_client.post(
        "/api/portfolio/add",
        json={"symbol": "TCS", "quantity": 5, "buy_price": 100.0},
        headers=HEADERS,
    )
    assert response.status_code == 200


def test_add_stock_appears_in_portfolio(app_client):
    """Stock added via /add appears in /api/portfolio list."""
    _add_stock(app_client, symbol="INFY")
    response = app_client.get("/api/portfolio", headers=HEADERS)
    data = response.json()
    symbols = [item["holding"]["symbol"] for item in data]
    assert "INFY" in symbols


# ── POST /api/portfolio/sell ─────────────────────────────────────────────────

def test_sell_stock_invalid_id_returns_404(app_client):
    """POST /api/portfolio/sell with non-existent holding_id returns 404."""
    response = app_client.post(
        "/api/portfolio/sell",
        json={
            "holding_id": "nonexistent-id",
            "quantity": 5,
            "sell_price": 3000.0,
        },
        headers=HEADERS,
    )
    assert response.status_code == 404


def test_sell_stock_missing_required_fields_returns_422(app_client):
    """POST /api/portfolio/sell without required fields returns 422."""
    response = app_client.post(
        "/api/portfolio/sell",
        json={"holding_id": "abc"},
        headers=HEADERS,
    )
    assert response.status_code == 422


def test_sell_stock_success(app_client):
    """Sell a stock that was previously added."""
    add_resp = _add_stock(app_client, symbol="TCS", qty=20, price=3500.0)
    holding_id = add_resp.json()["id"]

    sell_resp = app_client.post(
        "/api/portfolio/sell",
        json={
            "holding_id": holding_id,
            "quantity": 5,
            "sell_price": 4000.0,
            "sell_date": "2024-06-01",
        },
        headers=HEADERS,
    )
    assert sell_resp.status_code == 200
    data = sell_resp.json()
    assert "realized_pl" in data
    assert data["realized_pl"] == pytest.approx(2500.0)  # (4000-3500)*5


# ── DELETE /api/portfolio/{id} ───────────────────────────────────────────────

def test_delete_holding_not_found_returns_404(app_client):
    """DELETE /api/portfolio/{id} with unknown id returns 404."""
    response = app_client.delete("/api/portfolio/no-such-id", headers=HEADERS)
    assert response.status_code == 404


def test_delete_holding_success(app_client):
    """DELETE /api/portfolio/{id} removes a holding."""
    add_resp = _add_stock(app_client, symbol="WIPRO")
    holding_id = add_resp.json()["id"]

    del_resp = app_client.delete(f"/api/portfolio/{holding_id}", headers=HEADERS)
    assert del_resp.status_code == 200
    data = del_resp.json()
    assert "message" in data


def test_deleted_holding_not_in_portfolio(app_client):
    """After deletion the holding no longer appears in /api/portfolio."""
    add_resp = _add_stock(app_client, symbol="HDFCBANK")
    holding_id = add_resp.json()["id"]

    app_client.delete(f"/api/portfolio/{holding_id}", headers=HEADERS)

    portfolio = app_client.get("/api/portfolio", headers=HEADERS).json()
    ids = [item["holding"]["id"] for item in portfolio]
    assert holding_id not in ids


# ── GET /api/portfolio/stock-summary ────────────────────────────────────────

def test_stock_summary_returns_200(app_client):
    """GET /api/portfolio/stock-summary returns 200."""
    response = app_client.get("/api/portfolio/stock-summary", headers=HEADERS)
    assert response.status_code == 200


def test_stock_summary_returns_list(app_client):
    """GET /api/portfolio/stock-summary returns a list."""
    response = app_client.get("/api/portfolio/stock-summary", headers=HEADERS)
    assert isinstance(response.json(), list)


def test_stock_summary_after_add(app_client):
    """Stock summary contains added stock."""
    _add_stock(app_client, symbol="BAJFINANCE", qty=5, price=7000.0)
    response = app_client.get("/api/portfolio/stock-summary", headers=HEADERS)
    data = response.json()
    symbols = [item["symbol"] for item in data]
    assert "BAJFINANCE" in symbols


def test_stock_summary_item_shape(app_client):
    """Stock summary items have required fields."""
    _add_stock(app_client, symbol="ITCLTD", qty=100, price=450.0)
    response = app_client.get("/api/portfolio/stock-summary", headers=HEADERS)
    items = response.json()
    assert len(items) > 0
    item = items[0]
    assert "symbol" in item
    assert "exchange" in item
    assert "total_held_qty" in item
    assert "total_invested" in item


# ── GET /api/transactions ────────────────────────────────────────────────────

def test_get_transactions_returns_200(app_client):
    """GET /api/transactions returns 200."""
    response = app_client.get("/api/transactions", headers=HEADERS)
    assert response.status_code == 200


def test_get_transactions_returns_list(app_client):
    """GET /api/transactions returns a list."""
    response = app_client.get("/api/transactions", headers=HEADERS)
    assert isinstance(response.json(), list)
