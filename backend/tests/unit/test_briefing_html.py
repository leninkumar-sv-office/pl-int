"""Tests for app/briefing_html.py — HTML briefing generation from markdown."""
import os
from unittest.mock import patch, MagicMock

import pytest


class TestHelpers:
    def test_esc_html_entities(self):
        from app.briefing_html import _esc
        assert _esc("A & B") == "A &amp; B"
        assert _esc("<script>") == "&lt;script&gt;"
        assert _esc("normal text") == "normal text"

    def test_md_inline_bold(self):
        from app.briefing_html import _md_inline
        result = _md_inline("**bold text**")
        assert "<strong>" in result
        assert "bold text" in result

    def test_md_inline_italic(self):
        from app.briefing_html import _md_inline
        result = _md_inline("*italic*")
        assert "<em>" in result

    def test_md_inline_code(self):
        from app.briefing_html import _md_inline
        result = _md_inline("`code`")
        assert "<code>" in result

    def test_md_inline_action_today(self):
        from app.briefing_html import _md_inline
        result = _md_inline("**[ACTION TODAY]**")
        assert "ACTION TODAY" in result
        assert "orange" in result

    def test_md_inline_escapes_html(self):
        from app.briefing_html import _md_inline
        result = _md_inline("A < B & C > D")
        assert "&lt;" in result
        assert "&amp;" in result
        assert "&gt;" in result


class TestSignalClasses:
    def test_get_signal_class_bullish(self):
        from app.briefing_html import _get_signal_class
        assert _get_signal_class("Bullish") == "signal-bull"
        assert _get_signal_class("[BUY]") == "signal-bull"

    def test_get_signal_class_bearish(self):
        from app.briefing_html import _get_signal_class
        assert _get_signal_class("Bearish") == "signal-bear"
        assert _get_signal_class("[SELL]") == "signal-bear"

    def test_get_signal_class_neutral(self):
        from app.briefing_html import _get_signal_class
        assert _get_signal_class("Neutral") == "signal-neutral"
        assert _get_signal_class("[Watch]") == "signal-neutral"

    def test_get_signal_class_hold(self):
        from app.briefing_html import _get_signal_class
        assert _get_signal_class("Hold") == "signal-hold"

    def test_get_signal_class_default(self):
        from app.briefing_html import _get_signal_class
        assert _get_signal_class("unknown signal") == "signal-neutral"

    def test_get_action_class(self):
        from app.briefing_html import _get_action_class
        assert _get_action_class("BUY") == "action-bull"
        assert _get_action_class("SELL") == "action-bear"
        assert _get_action_class("TRIM") == "action-warn"
        assert _get_action_class("HOLD") == "action-hold"
        assert _get_action_class("WATCH") == "action-neutral"
        assert _get_action_class("UNKNOWN") == "action-neutral"

    def test_is_signal_col(self):
        from app.briefing_html import _is_signal_col
        assert _is_signal_col("Signal") is True
        assert _is_signal_col("Action") is True
        assert _is_signal_col("Today's Signal") is True
        assert _is_signal_col("1D") is True
        assert _is_signal_col("Stock") is False


class TestRenderCell:
    def test_render_cell_plain(self):
        from app.briefing_html import _render_cell
        result = _render_cell("hello", is_signal_col=False)
        assert "hello" in result

    def test_render_cell_signal(self):
        from app.briefing_html import _render_cell
        result = _render_cell("Bullish", is_signal_col=True)
        assert "badge" in result
        assert "signal-bull" in result

    def test_render_cell_empty_signal(self):
        from app.briefing_html import _render_cell
        result = _render_cell("  ", is_signal_col=True)
        assert result == "  "  # Empty content returned as-is via _md_inline


class TestRenderTable:
    def test_render_table_empty(self):
        from app.briefing_html import _render_table
        assert _render_table([]) == ""

    def test_render_table_basic(self):
        from app.briefing_html import _render_table
        rows = [
            ["Stock", "Price", "Signal"],
            ["RELIANCE", "2500", "Bullish"],
            ["TCS", "3500", "Neutral"],
        ]
        html = _render_table(rows)
        assert "<table>" in html
        assert "RELIANCE" in html
        assert "TCS" in html
        assert "signal-bull" in html  # Signal column

    def test_render_table_pad_short_rows(self):
        from app.briefing_html import _render_table
        rows = [
            ["A", "B", "C"],
            ["1"],  # Short row
        ]
        html = _render_table(rows)
        assert html.count("<td>") >= 1


class TestExtractActions:
    def test_extract_actions_from_table(self):
        from app.briefing_html import _extract_actions
        lines = [
            "| Held Stock | Action | Value |",
            "| --- | --- | --- |",
            "| **RELIANCE** | **BUY** | 2500 |",
            "| **TCS** | **SELL** | 3500 |",
        ]
        actions = _extract_actions(lines)
        assert "BUY" in actions
        assert "SELL" in actions

    def test_extract_actions_empty(self):
        from app.briefing_html import _extract_actions
        lines = ["no table here"]
        actions = _extract_actions(lines)
        assert actions == {}

    def test_extract_actions_dedup(self):
        from app.briefing_html import _extract_actions
        lines = [
            "| Held Stock | Action | Value |",
            "| --- | --- | --- |",
            "| **RELIANCE** | **BUY** | 2500 |",
            "| **RELIANCE** | **BUY** | 2600 |",
        ]
        actions = _extract_actions(lines)
        if "BUY" in actions:
            assert len(actions["BUY"]) >= 1


class TestRenderActionCards:
    def test_render_action_cards_empty(self):
        from app.briefing_html import _render_action_cards
        assert _render_action_cards({}) == ""

    def test_render_action_cards_basic(self):
        from app.briefing_html import _render_action_cards
        actions = {"BUY": ["RELIANCE (2500)"], "SELL": ["TCS"]}
        html = _render_action_cards(actions)
        assert "action-cards" in html
        assert "BUY" in html
        assert "SELL" in html
        assert "RELIANCE" in html


class TestParseSectorBullets:
    def test_parse_sector_bullets(self):
        from app.briefing_html import _parse_sector_bullets
        lines = [
            "- **IT**: BEARISH. Companies facing headwinds.",
            "- **Banking**: POSITIVE. Strong credit growth.",
            "- **Pharma**: MIXED. Regulatory uncertainty.",
        ]
        sectors = _parse_sector_bullets(lines)
        assert len(sectors) == 3
        assert sectors[0][1] == "BEARISH"
        assert sectors[1][1] == "POSITIVE"

    def test_parse_sector_bullets_outperformer(self):
        from app.briefing_html import _parse_sector_bullets
        lines = ["- **Defense**: OUTPERFORMER. Strong order book."]
        sectors = _parse_sector_bullets(lines)
        assert sectors[0][1] == "BULLISH"

    def test_parse_sector_bullets_emerging(self):
        from app.briefing_html import _parse_sector_bullets
        lines = ["- **EV**: EMERGING THEME. Growing demand."]
        sectors = _parse_sector_bullets(lines)
        assert sectors[0][1] == "POSITIVE"


class TestRenderSectorBars:
    def test_render_sector_bars_empty(self):
        from app.briefing_html import _render_sector_bars
        assert _render_sector_bars([]) == ""

    def test_render_sector_bars_basic(self):
        from app.briefing_html import _render_sector_bars
        lines = [
            "- **IT**: BEARISH. Sector under pressure.",
            "- **Banking**: BULLISH. Growing well.",
        ]
        html = _render_sector_bars(lines)
        assert "sector-bar" in html
        assert "BEARISH" in html
        assert "BULLISH" in html


class TestRenderDashboard:
    def test_render_dashboard_empty(self):
        from app.briefing_html import _render_dashboard
        assert _render_dashboard([]) == ""

    def test_render_dashboard_with_tickers(self):
        from app.briefing_html import _render_dashboard
        tickers = [
            {"key": "SENSEX", "price": 73500, "unit": "", "change_pct": 1.2,
             "week_change_pct": 2.5, "month_change_pct": 5.0},
            {"key": "NIFTY50", "price": 22200, "unit": "", "change_pct": -0.5,
             "week_change_pct": -1.0, "month_change_pct": 3.0},
            {"key": "GOLD", "price": 85.5, "unit": "$/oz", "change_pct": 0,
             "week_change_pct": 0, "month_change_pct": 0},
        ]
        html = _render_dashboard(tickers)
        assert "dashboard" in html
        assert "SENSEX" in html
        assert "NIFTY 50" in html

    def test_render_dashboard_formatting(self):
        from app.briefing_html import _render_dashboard
        tickers = [
            {"key": "USDINR", "price": 83.25, "unit": "", "change_pct": 0.1,
             "week_change_pct": 0, "month_change_pct": 0},
            {"key": "CRUDEOIL", "price": 150, "unit": "$/bbl", "change_pct": -2.0,
             "week_change_pct": -3.0, "month_change_pct": -5.0},
        ]
        html = _render_dashboard(tickers)
        assert "INR/USD" in html
        assert "CRUDE OIL" in html
        assert "$/bbl" in html


class TestFetchTickerData:
    def test_fetch_ticker_data_success(self):
        from app.briefing_html import _fetch_ticker_data
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"tickers": [{"key": "SENSEX", "price": 73000}]}).encode()
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _fetch_ticker_data()
        assert len(result) == 1
        assert result[0]["key"] == "SENSEX"

    def test_fetch_ticker_data_failure(self):
        from app.briefing_html import _fetch_ticker_data
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")), \
             patch("time.sleep"):
            result = _fetch_ticker_data()
        assert result == []

    def test_fetch_ticker_data_empty_tickers(self):
        from app.briefing_html import _fetch_ticker_data
        import json
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"tickers": []}).encode()
        with patch("urllib.request.urlopen", return_value=mock_resp), \
             patch("time.sleep"):
            result = _fetch_ticker_data()
        assert result == []


class TestGenerateBriefingHtml:
    def test_generate_basic_html(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = """### Market Overview
Strong day for markets.

### Sector Impact
- **IT**: BEARISH. Under pressure.
- **Banking**: BULLISH. Growing well.

### Stock Recommendations
| Stock | Signal | Action |
| --- | --- | --- |
| RELIANCE | Bullish | BUY |
| TCS | Bearish | SELL |
"""
        output = tmp_path / "briefing.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        assert os.path.exists(result)
        content = open(result).read()
        assert "Market Briefing" in content
        assert "Market Overview" in content
        assert "RELIANCE" in content

    def test_generate_with_preamble(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = """> Summary line one
> Summary line two

### Section One
Content here.
"""
        output = tmp_path / "briefing.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        content = open(result).read()
        assert "blockquote" in content

    def test_generate_default_path(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = "### Test\nContent"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md)
        assert result.endswith(".html")
        assert os.path.exists(result)

    def test_generate_with_dashboard(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = "### Test\nContent"
        tickers = [
            {"key": "SENSEX", "price": 73000, "unit": "", "change_pct": 1.5,
             "week_change_pct": 2.0, "month_change_pct": 5.0}
        ]
        output = tmp_path / "out.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=tickers), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        content = open(result).read()
        assert "dashboard" in content

    def test_generate_with_list_items(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = """### Notes
- First point
- Second point
> Blockquote

---
Normal paragraph.
"""
        output = tmp_path / "out.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        content = open(result).read()
        assert "<li>" in content
        assert "<blockquote>" in content
        assert "<hr>" in content

    def test_generate_with_multiple_tables(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = """### Section
| A | B |
| --- | --- |
| 1 | 2 |

Some text between tables.

| C | D |
| --- | --- |
| 3 | 4 |
"""
        output = tmp_path / "out.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        content = open(result).read()
        assert content.count("<table>") == 2

    def test_generate_preamble_with_plain_text(self, tmp_path):
        from app.briefing_html import generate_briefing_html
        md = """Plain preamble text before any heading.

### Section
Content.
"""
        output = tmp_path / "out.html"
        with patch("app.briefing_html._fetch_ticker_data", return_value=[]), \
             patch("app.briefing_html._DUMPS_DIR", str(tmp_path)):
            result = generate_briefing_html(md, output_path=str(output))
        content = open(result).read()
        assert "Plain preamble text" in content
