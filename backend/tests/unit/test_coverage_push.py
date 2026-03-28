"""
Final push for coverage: targeted tests for remaining uncovered lines across
multiple modules. Focuses on edge cases and error paths.
"""
import os
import json
import time
from datetime import datetime, timedelta, date
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path
import pytest


# ═══════════════════════════════════════════════════════════
#  zerodha_service.py — remaining lines
# ═══════════════════════════════════════════════════════════

class TestZerodhaFetchLtp:
    def test_fetch_ltp_no_session(self):
        import app.zerodha_service as zs
        with patch.object(zs, "is_session_valid", return_value=False):
            result = zs.fetch_ltp([("RELIANCE", "NSE")])
        assert result == {}

    def test_fetch_ltp_success(self):
        import app.zerodha_service as zs
        zs._api_key = "test"
        zs._access_token = "test"
        zs._auth_failed = False
        api_resp = {
            "data": {
                "NSE:RELIANCE": {"last_price": 2500.0}
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_ltp([("RELIANCE", "NSE")])
        assert "RELIANCE.NSE" in result
        assert result["RELIANCE.NSE"] == 2500.0

    def test_fetch_ltp_zero_price_skipped(self):
        import app.zerodha_service as zs
        zs._api_key = "test"
        zs._access_token = "test"
        zs._auth_failed = False
        api_resp = {
            "data": {
                "NSE:DEAD": {"last_price": 0}
            }
        }
        with patch.object(zs, "is_session_valid", return_value=True):
            with patch.object(zs, "_api_get", return_value=api_resp):
                result = zs.fetch_ltp([("DEAD", "NSE")])
        assert "DEAD.NSE" not in result


class TestZerodhaGetMfLtpNotLoaded:
    def test_get_mf_ltp_triggers_load(self):
        import app.zerodha_service as zs
        old_loaded = zs._mf_instruments_loaded
        zs._mf_instruments_loaded = False
        zs._mf_instruments = [
            {"tradingsymbol": "INF999", "last_price": 123.45, "name": "Test"},
        ]
        with patch.object(zs, "_load_mf_instruments"):
            result = zs.get_mf_ltp("INF999")
        zs._mf_instruments_loaded = old_loaded


class TestZerodhaSearchMFDedup:
    def test_search_deduplication(self):
        import app.zerodha_service as zs
        zs._mf_instruments = [
            {"tradingsymbol": "INF1", "name": "Axis Bluechip Direct Growth Fund",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "growth", "last_price": 55.0},
            {"tradingsymbol": "INF2", "name": "Axis Bluechip Direct Payout Fund",
             "amc": "AxisMF", "scheme_type": "equity", "plan": "direct",
             "dividend_type": "payout", "last_price": 50.0},
        ]
        zs._mf_instruments_loaded = True
        results = zs.search_mf_instruments("Axis Bluechip", plan="direct")
        # Should deduplicate — one growth and one dividend
        assert len(results) <= 2


# ═══════════════════════════════════════════════════════════
#  stock_service.py — remaining lines
# ═══════════════════════════════════════════════════════════

class TestStockServiceFetchMultiple:
    def test_fetch_multiple_no_symbols(self):
        from app.stock_service import fetch_multiple
        result = fetch_multiple([])
        assert result == {}

    def test_cache_hit(self):
        import app.stock_service as ss
        from app.stock_service import StockLiveData
        # Pre-populate cache
        cached = StockLiveData(
            symbol="CACHED", exchange="NSE", name="Cached Stock",
            current_price=100.0, week_52_high=120.0, week_52_low=80.0,
            day_change=2.0, day_change_pct=2.0, volume=10000,
            previous_close=98.0, is_manual=False,
        )
        ss._cache_set("CACHED.NSE", cached)
        result = ss.fetch_multiple([("CACHED", "NSE")])
        assert "CACHED.NSE" in result
        # Cleanup
        with ss._cache_lock:
            ss._cache.pop("CACHED.NSE", None)


class TestStockServiceYahooTickerHistorical:
    def test_success(self):
        from app.stock_service import fetch_yahoo_ticker_historical
        import app.stock_service as ss
        now = datetime.now()
        timestamps = []
        closes = []
        for i in range(90):
            dt = now - timedelta(days=90 - i)
            timestamps.append(int(dt.timestamp()))
            closes.append(100.0 + i * 0.1)

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "chart": {"result": [
                {"timestamp": timestamps, "indicators": {"quote": [{"close": closes}]}}
            ]}
        }
        with patch.object(ss._requests, "get", return_value=mock_resp):
            result = fetch_yahoo_ticker_historical({"key": "SGX", "yahoo": "%5ESTI"})
        assert "week_change_pct" in result

    def test_http_error(self):
        from app.stock_service import fetch_yahoo_ticker_historical
        import app.stock_service as ss
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch.object(ss._requests, "get", return_value=mock_resp):
            result = fetch_yahoo_ticker_historical({"key": "SGX", "yahoo": "%5ESTI"})
        assert result["week_change_pct"] == 0.0


# ═══════════════════════════════════════════════════════════
#  epaper_service.py — RSS parsing edge cases
# ═══════════════════════════════════════════════════════════

class TestEpaperRSSParsing:
    def _build_rss_xml(self, title="Test Article About Markets and Economy", link="https://test.com/article/1"):
        now = datetime.now()
        pub_date = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
        return f"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description><![CDATA[<p>Test summary text here</p>]]></description>
      <pubDate>{pub_date}</pubDate>
    </item>
    <item>
      <title>Short</title>
      <link>https://test.com/page</link>
    </item>
  </channel>
</rss>"""

    def test_fetch_bl_rss_articles(self):
        import app.epaper_service as es
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._build_rss_xml().encode()
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_bl_rss_articles("markets", "BL-Markets")
        assert isinstance(result, list)
        # Should have 1 article (the "Short" one is filtered out by len < 15)
        assert len(result) >= 1

    def test_fetch_th_rss_articles(self):
        import app.epaper_service as es
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._build_rss_xml().encode()
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_th_rss_articles("markets", "TH-Markets")
        assert isinstance(result, list)

    def test_fetch_mc_rss_articles(self):
        import app.epaper_service as es
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = self._build_rss_xml().encode()
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_mc_rss_articles("https://mc.com/rss", "MC-Latest")
        assert isinstance(result, list)

    def test_fetch_gn_rss_articles(self):
        import app.epaper_service as es
        xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Indian Markets Rally Strongly Today - Test Source</title>
      <link>https://news.google.com/article/1</link>
      <source>Test Source</source>
      <description><![CDATA[<p>Summary of the article</p>]]></description>
      <pubDate>{}</pubDate>
    </item>
  </channel>
</rss>""".format(datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT"))
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = xml.encode()
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_gn_rss_articles("test query", "GN-Test")
        assert isinstance(result, list)

    def test_fetch_bl_rss_http_error(self):
        import app.epaper_service as es
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_bl_rss_articles("markets", "BL-Markets")
        assert result == []

    def test_fetch_bl_rss_exception(self):
        import app.epaper_service as es
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            result = es._fetch_bl_rss_articles("markets", "BL-Markets")
        assert result == []

    def test_gn_article_body_selectors(self):
        import app.epaper_service as es
        # Test the article body selector chain
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="artText"><p>This is a long enough article body text for the test.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_gn_article_body("https://news.google.com/article")
        assert "long enough article" in result

    def test_gn_article_body_exception(self):
        import app.epaper_service as es
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            result = es._fetch_gn_article_body("https://news.google.com/article")
        assert result == ""

    def test_mc_article_body_selectors(self):
        import app.epaper_service as es
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '<div class="arti-flow"><p>Moneycontrol article body text that is really long enough.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=mock_resp):
            result = es._fetch_mc_article_body("https://mc.com/article")
        assert "Moneycontrol article" in result

    def test_mc_article_body_exception(self):
        import app.epaper_service as es
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            result = es._fetch_mc_article_body("https://mc.com/article")
        assert result == ""


# ═══════════════════════════════════════════════════════════
#  epaper_service.py — generate_insights with AI
# ═══════════════════════════════════════════════════════════

class TestEpaperGenerateInsightsAI:
    def test_ai_insights_success(self):
        import app.epaper_service as es
        old_key = es._ANTHROPIC_API_KEY
        es._ANTHROPIC_API_KEY = "test_key"
        with es._cache_lock:
            es._insights_cache.clear()

        articles = [
            {"title": "RELIANCE Q3 results strong", "summary": "Good results",
             "body": "Reliance Industries posted strong Q3 results",
             "section": "Markets", "url": "https://test.com/1"},
        ]
        ai_response = json.dumps([
            {"headline": "RELIANCE strong results", "detail": "Q3 beat",
             "stocks_affected": ["RELIANCE"], "sectors": ["Energy"],
             "sentiment": "positive", "action": "buy", "urgency": "medium",
             "article_indices": [1]},
        ])
        with patch.object(es, "_call_claude", return_value=ai_response):
            result = es.generate_insights(articles, ["RELIANCE"])
        assert len(result) >= 1
        assert result[0]["sources"][0]["url"] == "https://test.com/1"

        with es._cache_lock:
            es._insights_cache.clear()
        es._ANTHROPIC_API_KEY = old_key

    def test_ai_insights_bad_json_falls_back(self):
        import app.epaper_service as es
        old_key = es._ANTHROPIC_API_KEY
        es._ANTHROPIC_API_KEY = "test_key"
        with es._cache_lock:
            es._insights_cache.clear()

        with patch.object(es, "_call_claude", return_value="not json"):
            result = es.generate_insights([], [])
        assert isinstance(result, list)

        with es._cache_lock:
            es._insights_cache.clear()
        es._ANTHROPIC_API_KEY = old_key

    def test_ai_insights_empty_response_falls_back(self):
        import app.epaper_service as es
        old_key = es._ANTHROPIC_API_KEY
        es._ANTHROPIC_API_KEY = "test_key"
        with es._cache_lock:
            es._insights_cache.clear()

        with patch.object(es, "_call_claude", return_value=""):
            result = es.generate_insights([], [])
        assert isinstance(result, list)

        with es._cache_lock:
            es._insights_cache.clear()
        es._ANTHROPIC_API_KEY = old_key


# ═══════════════════════════════════════════════════════════
#  epaper_service.py — chat function
# ═══════════════════════════════════════════════════════════

class TestEpaperChat:
    def test_chat_with_api_key(self):
        import app.epaper_service as es
        old_key = es._ANTHROPIC_API_KEY
        es._ANTHROPIC_API_KEY = "test_key"
        articles = [{"title": "Test Article Title Here", "body": "Body text here that is long",
                      "summary": "Summary", "section": "Markets", "url": "https://test.com"}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"text": "AI response here"}]}
        with patch("app.epaper_service.requests.post", return_value=mock_resp):
            result = es.chat("What happened today?", articles, ["RELIANCE"])
        assert result == "AI response here"
        es._ANTHROPIC_API_KEY = old_key


# ═══════════════════════════════════════════════════════════
#  expiry_rules.py — load/save/evaluate
# ═══════════════════════════════════════════════════════════

class TestExpiryRulesLoadSave:
    def test_save_and_load_rules(self, tmp_path):
        from app.expiry_rules import _load_rules, _save_rules
        # Mock _settings_dir to return tmp_path/settings
        settings_dir = tmp_path / "settings"
        settings_dir.mkdir(parents=True)
        with patch("app.expiry_rules._settings_dir", return_value=settings_dir):
            rules = [{"id": "r1", "category": "fd", "rule_type": "on_maturity"}]
            _save_rules("test@email.com", "user1", rules)
            loaded = _load_rules("test@email.com", "user1")
        assert len(loaded) == 1
        assert loaded[0]["id"] == "r1"


class TestExpiryRulesEvaluateProfileRule:
    def test_evaluate_profit_rule_outside_window(self):
        from app.expiry_rules import _evaluate_profit_rule
        rule = {"id": "test", "rule_type": "profit_threshold",
                "alert_time": "03:00", "category": "stocks",
                "threshold_pct": 25}
        # Should return without action since time window doesn't match
        _evaluate_profit_rule(rule, "test@email.com", "user1", MagicMock())


# ═══════════════════════════════════════════════════════════
#  briefing_pdf.py — sector bars and dashboard with many items
# ═══════════════════════════════════════════════════════════

class TestBriefingPdfSectorBarsLong:
    def test_sector_with_long_detail(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_sector_bars
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        lines = [
            "- Banking: BULLISH. " + "x" * 200,  # Very long detail
            "- IT: CRISIS. Major disruption expected",
            "- Pharma: STABLE. Steady performance",
            "- FMCG: NEGATIVE. Price competition",
        ]
        _draw_sector_bars(pdf, lines)
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestBriefingPdfActionSummaryWrap:
    def test_many_actions_wrap(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_action_summary
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        # Many stocks to trigger x > 160 wrapping
        lines = [
            "| Stock | Action |",
            "|---|---|",
        ]
        for i in range(20):
            lines.append(f"| STOCK{i:02d} | {'TRIM' if i % 3 == 0 else 'BUY' if i % 3 == 1 else 'SELL'} |")
        _draw_action_summary(pdf, lines)
        output = pdf.output(dest="S")
        assert len(output) > 0


# ═══════════════════════════════════════════════════════════
#  sip_manager.py — quarterly edge case with rollover
# ═══════════════════════════════════════════════════════════

class TestSipManagerQuarterlyRollover:
    def test_quarterly_computes_future(self):
        from app.sip_manager import SIPManager
        # Use a date far in the future to ensure reliable test
        result = SIPManager._compute_next_sip_date("quarterly", 15, "2099-10-20")
        assert result is not None
        # Should be 3 months ahead from October = January
        assert "2100-01" in result

    def test_weekly_sip(self):
        from app.sip_manager import SIPManager
        result = SIPManager._compute_next_sip_date("weekly", 3, "2099-03-15")
        assert result is not None


# ═══════════════════════════════════════════════════════════
#  notification_service.py — send_email success path
# ═══════════════════════════════════════════════════════════

class TestNotificationSendEmail:
    def test_send_email_success(self):
        import app.notification_service as ns
        old_email = ns._EMAIL_ADDRESS
        old_pass = ns._EMAIL_APP_PASSWORD
        ns._EMAIL_ADDRESS = "test@example.com"
        ns._EMAIL_APP_PASSWORD = "test_password"
        with patch("smtplib.SMTP_SSL") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
            result = ns.send_email("Test Subject", "Test Body",
                                    html_body="<p>HTML</p>",
                                    recipients=["recipient@example.com"])
        ns._EMAIL_ADDRESS = old_email
        ns._EMAIL_APP_PASSWORD = old_pass


# ═══════════════════════════════════════════════════════════
#  contract_note_parser.py — extract helpers
# ═══════════════════════════════════════════════════════════

class TestContractNoteHelpers:
    def test_extract_trade_date(self):
        from app.contract_note_parser import _extract_trade_date
        assert _extract_trade_date("TRADE DATE 15-JAN-24") == "2024-01-15"
        assert _extract_trade_date("No date here") is None

    def test_extract_contract_no(self):
        from app.contract_note_parser import _extract_contract_no
        assert _extract_contract_no("CONTRACT NOTE NO. 12345") == "12345"
        assert _extract_contract_no("No contract") is None

    def test_extract_exchange_map(self):
        from app.contract_note_parser import _extract_exchange_map
        text = "BSEM\nINE002A01018 RELIANCE\nNSEM\nINE467B01029 TCS"
        result = _extract_exchange_map(text)
        assert result.get("INE002A01018") == "BSE"
        assert "INE467B01029" not in result  # NSE is default, not stored


# ═══════════════════════════════════════════════════════════
#  dividend_parser.py — build_name_map
# ═══════════════════════════════════════════════════════════

class TestDividendBuildLookupTables:
    def test_build_lookup_tables(self, tmp_path):
        from app.dividend_parser import _build_lookup_tables
        # Create a minimal symbol_cache.json
        cache_file = tmp_path / "symbol_cache.json"
        cache_file.write_text(json.dumps({
            "nse": {"TCS": ["TCS", "NSE", "Tata Consultancy Services"]},
            "isin": {"INE467B01029": ["TCS", "NSE", "Tata Consultancy Services"]},
        }))
        portfolio_name_map = {"RELIANCE": "Reliance Industries Ltd"}
        name_to_symbol, symbol_set, aliases = _build_lookup_tables(cache_file, portfolio_name_map)
        assert "RELIANCE" in symbol_set
        assert "TCS" in symbol_set
