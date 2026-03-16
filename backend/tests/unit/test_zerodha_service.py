"""
Unit tests for app/zerodha_service.py

Tests session management, API call wrappers, and quote fetching.
KiteConnect and all requests are mocked.
"""
import hashlib
from unittest.mock import MagicMock, patch

import pytest


# ─── helpers ────────────────────────────────────────────────────────────────

def _reset_globals():
    import app.zerodha_service as zs
    zs._access_token = "test_token"
    zs._api_key = "test_api_key"
    zs._api_secret = "test_secret"
    zs._auth_failed = False
    zs._conn_failed = False
    zs._session_valid = True
    zs._last_error = ""


def _clear_session():
    import app.zerodha_service as zs
    zs._access_token = ""
    zs._api_key = ""
    zs._auth_failed = False
    zs._conn_failed = False
    zs._session_valid = False


# ═══════════════════════════════════════════════════════════
#  is_configured / is_session_valid
# ═══════════════════════════════════════════════════════════

def test_is_configured_true():
    import app.zerodha_service as zs
    _reset_globals()
    assert zs.is_configured() is True


def test_is_configured_false():
    import app.zerodha_service as zs
    zs._api_key = ""
    try:
        assert zs.is_configured() is False
    finally:
        zs._api_key = "test_api_key"


def test_is_session_valid_with_token():
    import app.zerodha_service as zs
    _reset_globals()
    # Prevent auto-login attempts
    with patch.object(zs, "can_auto_login", return_value=False):
        assert zs.is_session_valid() is True


def test_is_session_valid_no_token():
    import app.zerodha_service as zs
    _clear_session()
    with patch.object(zs, "can_auto_login", return_value=False):
        assert zs.is_session_valid() is False


def test_is_session_valid_auth_failed():
    import app.zerodha_service as zs
    _reset_globals()
    zs._auth_failed = True
    with patch.object(zs, "can_auto_login", return_value=False):
        assert zs.is_session_valid() is False
    zs._auth_failed = False


# ═══════════════════════════════════════════════════════════
#  _kite_instrument — symbol mapping
# ═══════════════════════════════════════════════════════════

def test_kite_instrument_normal():
    from app.zerodha_service import _kite_instrument
    assert _kite_instrument("RELIANCE", "NSE") == "NSE:RELIANCE"


def test_kite_instrument_bse():
    from app.zerodha_service import _kite_instrument
    assert _kite_instrument("500325", "BSE") == "BSE:500325"


def test_kite_instrument_override_majesco():
    from app.zerodha_service import _kite_instrument
    assert _kite_instrument("MAJESCO", "NSE") == "NSE:AURUM"


def test_kite_instrument_override_setfgold():
    from app.zerodha_service import _kite_instrument
    assert _kite_instrument("SBIETF", "NSE") == "NSE:SETFGOLD"


def test_kite_instrument_invalid_exchange():
    from app.zerodha_service import _kite_instrument
    # Invalid exchange defaults to NSE
    result = _kite_instrument("TCS", "INVALID")
    assert result == "NSE:TCS"


# ═══════════════════════════════════════════════════════════
#  set_access_token
# ═══════════════════════════════════════════════════════════

def test_set_access_token():
    import app.zerodha_service as zs
    with patch.object(zs, "_update_env"):
        zs.set_access_token("new_token_abc")
    assert zs._access_token == "new_token_abc"
    assert zs._auth_failed is False


def test_set_access_token_empty():
    import app.zerodha_service as zs
    with patch.object(zs, "_update_env"):
        zs.set_access_token("")
    assert zs._session_valid is False


# ═══════════════════════════════════════════════════════════
#  _api_get — mocked requests.get
# ═══════════════════════════════════════════════════════════

def test_api_get_success():
    import app.zerodha_service as zs
    _reset_globals()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"price": 2500}}
    with patch("app.zerodha_service.requests.get", return_value=mock_resp), \
         patch.object(zs, "can_auto_login", return_value=False):
        result = zs._api_get("/quote/ltp")
    assert result == {"data": {"price": 2500}}


def test_api_get_403_sets_auth_failed():
    import app.zerodha_service as zs
    _reset_globals()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Invalid token"
    with patch("app.zerodha_service.requests.get", return_value=mock_resp), \
         patch.object(zs, "_try_auto_login_and_retry", return_value=None):
        result = zs._api_get("/quote/ltp")
    assert result is None
    assert zs._auth_failed is True
    zs._auth_failed = False


def test_api_get_no_api_key():
    import app.zerodha_service as zs
    old_key = zs._api_key
    zs._api_key = ""
    try:
        result = zs._api_get("/quote/ltp")
        assert result is None
    finally:
        zs._api_key = old_key


def test_api_get_429_rate_limited():
    import app.zerodha_service as zs
    _reset_globals()
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    with patch("app.zerodha_service.requests.get", return_value=mock_resp), \
         patch("time.sleep"):
        result = zs._api_get("/quote/ltp")
    assert result is None


# ═══════════════════════════════════════════════════════════
#  fetch_ltp
# ═══════════════════════════════════════════════════════════

def test_fetch_ltp_success():
    import app.zerodha_service as zs
    _reset_globals()
    api_response = {
        "data": {
            "NSE:RELIANCE": {"last_price": 2500.0},
            "NSE:TCS": {"last_price": 3600.0},
        }
    }
    with patch.object(zs, "_api_get", return_value=api_response), \
         patch.object(zs, "is_session_valid", return_value=True):
        result = zs.fetch_ltp([("RELIANCE", "NSE"), ("TCS", "NSE")])
    assert result["RELIANCE.NSE"] == 2500.0
    assert result["TCS.NSE"] == 3600.0


def test_fetch_ltp_no_session():
    import app.zerodha_service as zs
    with patch.object(zs, "is_session_valid", return_value=False):
        result = zs.fetch_ltp([("RELIANCE", "NSE")])
    assert result == {}


def test_fetch_ltp_zero_price_filtered():
    import app.zerodha_service as zs
    _reset_globals()
    api_response = {
        "data": {
            "NSE:RELIANCE": {"last_price": 0},
        }
    }
    with patch.object(zs, "_api_get", return_value=api_response), \
         patch.object(zs, "is_session_valid", return_value=True):
        result = zs.fetch_ltp([("RELIANCE", "NSE")])
    assert "RELIANCE.NSE" not in result


# ═══════════════════════════════════════════════════════════
#  fetch_quotes
# ═══════════════════════════════════════════════════════════

def test_fetch_quotes_success():
    import app.zerodha_service as zs
    _reset_globals()
    api_response = {
        "data": {
            "NSE:INFY": {
                "last_price": 1800.0,
                "ohlc": {"open": 1780.0, "high": 1820.0, "low": 1770.0, "close": 1790.0},
                "volume": 500000,
            }
        }
    }
    with patch.object(zs, "_api_get", return_value=api_response), \
         patch.object(zs, "is_session_valid", return_value=True):
        result = zs.fetch_quotes([("INFY", "NSE")])
    assert "INFY.NSE" in result
    q = result["INFY.NSE"]
    assert q["price"] == 1800.0
    assert q["volume"] == 500000
    assert q["day_change"] == pytest.approx(10.0, abs=0.01)


def test_fetch_quotes_no_session():
    import app.zerodha_service as zs
    with patch.object(zs, "is_session_valid", return_value=False):
        result = zs.fetch_quotes([("INFY", "NSE")])
    assert result == {}


def test_fetch_quotes_api_failure_retries():
    """fetch_quotes retries once on API failure."""
    import app.zerodha_service as zs
    _reset_globals()
    call_count = [0]
    def fake_api_get(path, params=None):
        call_count[0] += 1
        return None  # always fail

    with patch.object(zs, "_api_get", side_effect=fake_api_get), \
         patch.object(zs, "is_session_valid", return_value=True), \
         patch("time.sleep"):
        result = zs.fetch_quotes([("RELIANCE", "NSE")])
    assert result == {}
    assert call_count[0] == 2  # tried twice


# ═══════════════════════════════════════════════════════════
#  fetch_ohlc
# ═══════════════════════════════════════════════════════════

def test_fetch_ohlc_success():
    import app.zerodha_service as zs
    _reset_globals()
    api_response = {
        "data": {
            "NSE:HDFC": {
                "last_price": 1500.0,
                "ohlc": {"open": 1490.0, "high": 1510.0, "low": 1480.0, "close": 1495.0},
            }
        }
    }
    with patch.object(zs, "_api_get", return_value=api_response), \
         patch.object(zs, "is_session_valid", return_value=True):
        result = zs.fetch_ohlc([("HDFC", "NSE")])
    assert "HDFC.NSE" in result
    assert result["HDFC.NSE"]["price"] == 1500.0
    assert result["HDFC.NSE"]["open"] == 1490.0


def test_fetch_ohlc_no_session():
    import app.zerodha_service as zs
    with patch.object(zs, "is_session_valid", return_value=False):
        assert zs.fetch_ohlc([("HDFC", "NSE")]) == {}


# ═══════════════════════════════════════════════════════════
#  generate_session
# ═══════════════════════════════════════════════════════════

def test_generate_session_success():
    import app.zerodha_service as zs
    _reset_globals()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": {"access_token": "new_access_token_xyz"}}
    with patch("app.zerodha_service.requests.post", return_value=mock_resp), \
         patch.object(zs, "_update_env"):
        result = zs.generate_session("some_request_token")
    assert result is True
    assert zs._access_token == "new_access_token_xyz"


def test_generate_session_failure():
    import app.zerodha_service as zs
    _reset_globals()
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_resp.text = "Invalid"
    with patch("app.zerodha_service.requests.post", return_value=mock_resp):
        result = zs.generate_session("bad_token")
    assert result is False


def test_generate_session_no_credentials():
    import app.zerodha_service as zs
    old_key = zs._api_key
    old_secret = zs._api_secret
    zs._api_key = ""
    zs._api_secret = ""
    try:
        result = zs.generate_session("token")
        assert result is False
    finally:
        zs._api_key = old_key
        zs._api_secret = old_secret


# ═══════════════════════════════════════════════════════════
#  get_login_url
# ═══════════════════════════════════════════════════════════

def test_get_login_url():
    import app.zerodha_service as zs
    _reset_globals()
    url = zs.get_login_url()
    assert "kite.zerodha.com" in url
    assert zs._api_key in url


# ═══════════════════════════════════════════════════════════
#  can_auto_login
# ═══════════════════════════════════════════════════════════

def test_can_auto_login_missing_credentials():
    import app.zerodha_service as zs
    old_vals = (zs._user_id, zs._password, zs._totp_secret)
    zs._user_id = ""
    zs._password = ""
    zs._totp_secret = ""
    try:
        assert zs.can_auto_login() is False
    finally:
        zs._user_id, zs._password, zs._totp_secret = old_vals


# ═══════════════════════════════════════════════════════════
#  fetch_52_week_range — session guard
# ═══════════════════════════════════════════════════════════

def test_fetch_52_week_range_no_session():
    import app.zerodha_service as zs
    with patch.object(zs, "is_session_valid", return_value=False):
        result = zs.fetch_52_week_range([("RELIANCE", "NSE")])
    assert result == {}
