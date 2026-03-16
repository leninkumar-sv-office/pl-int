"""Integration tests for market ticker endpoint."""

import pytest

HEADERS = {"X-User-Id": "testuser"}


def test_market_ticker_returns_200(app_client):
    """GET /api/market-ticker returns 200."""
    response = app_client.get("/api/market-ticker", headers=HEADERS)
    assert response.status_code == 200


def test_market_ticker_response_shape(app_client):
    """Market ticker response has 'tickers' key."""
    response = app_client.get("/api/market-ticker", headers=HEADERS)
    data = response.json()
    assert "tickers" in data


def test_market_ticker_tickers_is_list(app_client):
    """Tickers field is a list."""
    response = app_client.get("/api/market-ticker", headers=HEADERS)
    data = response.json()
    assert isinstance(data["tickers"], list)


def test_market_ticker_last_updated_field_present(app_client):
    """Response includes last_updated field (may be null)."""
    response = app_client.get("/api/market-ticker", headers=HEADERS)
    data = response.json()
    assert "last_updated" in data


def test_market_ticker_ticker_shape_when_populated(app_client):
    """If tickers are returned, each has required fields."""
    # First push some ticker data
    app_client.post(
        "/api/market-ticker/update",
        json=[
            {
                "key": "SENSEX",
                "label": "Sensex",
                "type": "index",
                "unit": "",
                "price": 72000.0,
                "change": 150.0,
                "change_pct": 0.21,
            }
        ],
        headers=HEADERS,
    )

    response = app_client.get("/api/market-ticker", headers=HEADERS)
    data = response.json()
    tickers = data["tickers"]
    # At least one ticker should be present now
    assert len(tickers) > 0
    # Check shape of a ticker
    ticker = tickers[0]
    assert "key" in ticker
    assert "label" in ticker
    assert "price" in ticker


def test_market_ticker_update_returns_count(app_client):
    """POST /api/market-ticker/update returns updated count."""
    response = app_client.post(
        "/api/market-ticker/update",
        json=[
            {"key": "NIFTY50", "label": "Nifty 50", "type": "index", "price": 21800.0, "change": -50.0, "change_pct": -0.23},
            {"key": "GOLD", "label": "Gold", "type": "commodity", "price": 6200.0, "change": 10.0, "change_pct": 0.16},
        ],
        headers=HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert "updated" in data
    assert data["updated"] == 2


def test_market_ticker_refresh_no_error(app_client):
    """POST /api/market-ticker/refresh returns 200."""
    response = app_client.post("/api/market-ticker/refresh", headers=HEADERS)
    assert response.status_code == 200


def test_market_ticker_no_auth_required(app_client):
    """Market ticker endpoint works without auth in local mode."""
    response = app_client.get("/api/market-ticker")
    assert response.status_code == 200
