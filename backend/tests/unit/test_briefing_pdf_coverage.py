"""
Unit tests for app/briefing_pdf.py — targeting uncovered lines.
Tests markdown-to-PDF rendering, metric extraction, dashboard rendering,
table parsing, signal styles, and the main generate function.
"""
import os
import re
from unittest.mock import patch, MagicMock
import pytest


class TestClean:
    def test_strip_bold_markdown(self):
        from app.briefing_pdf import _clean
        assert _clean("**bold text**") == "bold text"

    def test_strip_italic(self):
        from app.briefing_pdf import _clean
        assert _clean("*italic text*") == "italic text"

    def test_strip_code_backticks(self):
        from app.briefing_pdf import _clean
        assert _clean("`code`") == "code"

    def test_replace_unicode(self):
        from app.briefing_pdf import _clean
        assert "\u2014" not in _clean("em\u2014dash")
        assert "\u2019" not in _clean("it\u2019s")
        assert "\u20b9" not in _clean("\u20b9100")

    def test_action_today_marker(self):
        from app.briefing_pdf import _clean
        result = _clean("**[ACTION TODAY]** Do something")
        assert "[ACTION TODAY]" in result

    def test_arrow_replacement(self):
        from app.briefing_pdf import _clean
        assert "->" in _clean("\u2192 next")


class TestGetSignalStyle:
    def test_bullish(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("BULLISH")
        assert bg[1] > bg[0]  # greenish

    def test_bearish(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("[BEARISH]")
        assert bg[0] > bg[1]  # reddish

    def test_neutral(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("Neutral")

    def test_unknown(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("UNKNOWN_SIGNAL")
        assert bg == (235, 235, 235)

    def test_buy(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("Buy")
        assert tc == (0, 100, 0)

    def test_sell(self):
        from app.briefing_pdf import _get_signal_style
        bg, tc = _get_signal_style("Sell")
        assert tc == (160, 0, 0)


class TestExtractMetrics:
    def test_concise_format(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["Sensex: 76,034 (-1.08%)  Nifty: 23,639 (-0.95%)"]
        metrics = _extract_metrics(lines)
        assert len(metrics) >= 2
        sensex = [m for m in metrics if m[0] == "SENSEX"]
        assert len(sensex) == 1
        assert sensex[0][2] == pytest.approx(-1.08)

    def test_verbose_format(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["The Sensex plunged 1.08% to 76,034 amid heavy selling"]
        metrics = _extract_metrics(lines)
        sensex = [m for m in metrics if m[0] == "SENSEX"]
        if sensex:
            assert sensex[0][2] < 0

    def test_gift_nifty(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["GIFT Nifty: 23,718 (-0.9%)"]
        metrics = _extract_metrics(lines)
        gn = [m for m in metrics if m[0] == "GIFT NIFTY"]
        assert len(gn) == 1

    def test_brent_crude(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["Brent crude at $100.27 (+2.5%)"]
        metrics = _extract_metrics(lines)
        brent = [m for m in metrics if m[0] == "BRENT"]
        assert len(brent) == 1

    def test_gold(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["Gold at $5,154 (-0.4%)"]
        metrics = _extract_metrics(lines)
        gold = [m for m in metrics if m[0] == "GOLD"]
        assert len(gold) == 1

    def test_rupee(self):
        from app.briefing_pdf import _extract_metrics
        lines = ["INR/USD: 92.17 (-1%)"]
        metrics = _extract_metrics(lines)
        rupee = [m for m in metrics if m[0] == "INR/USD"]
        assert len(rupee) == 1

    def test_empty_lines(self):
        from app.briefing_pdf import _extract_metrics
        assert _extract_metrics([]) == []


class TestBuildDashboardMetrics:
    def test_with_tickers(self):
        from app.briefing_pdf import _build_dashboard_metrics
        tickers = [
            {"key": "SENSEX", "price": 76034, "change_pct": -1.08, "week_change_pct": 2.0, "month_change_pct": -3.0, "unit": ""},
            {"key": "NIFTY50", "price": 23639, "change_pct": -0.95, "unit": ""},
        ]
        result = _build_dashboard_metrics(tickers, [])
        assert len(result) >= 2
        assert result[0][0] == "SENSEX"
        assert "76,034" in result[0][1]

    def test_without_tickers_fallback(self):
        from app.briefing_pdf import _build_dashboard_metrics
        text_metrics = [("SENSEX", "76,034", -1.08)]
        result = _build_dashboard_metrics([], text_metrics)
        assert len(result) == 1
        assert result[0][3] is None  # No 1W data

    def test_small_price_formatting(self):
        from app.briefing_pdf import _build_dashboard_metrics
        tickers = [
            {"key": "USDINR", "price": 85.23, "change_pct": 0.1, "unit": "", "week_change_pct": None, "month_change_pct": None},
        ]
        result = _build_dashboard_metrics(tickers, [])
        assert len(result) >= 1


class TestBriefingPDF:
    def test_header_footer(self):
        from app.briefing_pdf import BriefingPDF
        pdf = BriefingPDF("Test Title")
        pdf.alias_nb_pages()
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        pdf.cell(0, 10, "Test content")
        # Just verify no exception
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestGenerateBriefingPdf:
    def test_simple_markdown(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Test Briefing\n\nSome content here.\n\n## Section 2\n\n- Bullet point 1\n- Bullet point 2"
        output_path = str(tmp_path / "test.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)
        assert filepath == output_path

    def test_with_table(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Report\n\n| Stock | Signal | Action | Source | Detail |\n|---|---|---|---|---|\n| RELIANCE | Bullish | Buy | BL | Strong momentum |\n| TCS | Bearish | Sell | TH | Weak outlook |"
        output_path = str(tmp_path / "table.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_sector_bars(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Report\n\nIT: BULLISH\nPharma: BEARISH\nBanking: MIXED"
        output_path = str(tmp_path / "sector.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_default_output_path(self):
        from app.briefing_pdf import generate_briefing_pdf
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf("# Test\n\nContent")
        assert os.path.exists(filepath)
        os.unlink(filepath)

    def test_with_numbered_list(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Numbers\n\n1. First item\n2. Second item\n3. Third item"
        output_path = str(tmp_path / "numbered.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_horizontal_rule(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Section 1\n\n---\n\n## Section 2\n\nContent after rule."
        output_path = str(tmp_path / "hr.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_empty_markdown(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        output_path = str(tmp_path / "empty.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf("", output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_market_overview(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Market Briefing\n\n## Market Overview\n\nSensex: 76,034 (-1.08%)  Nifty: 23,639 (-0.95%)\n\n## Recommendations"
        output_path = str(tmp_path / "overview.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_blockquote(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "# Test\n\n> This is a blockquote with important info\n> spanning multiple lines\n\nNormal text."
        output_path = str(tmp_path / "quote.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)


class TestFetchTickerData:
    def test_success(self):
        import urllib.request
        from app.briefing_pdf import _fetch_ticker_data
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"tickers": [{"key": "SENSEX", "price": 72000}]}'
        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            tickers = _fetch_ticker_data()
            assert len(tickers) == 1

    def test_failure_retries(self):
        import urllib.request
        from app.briefing_pdf import _fetch_ticker_data
        with patch.object(urllib.request, "urlopen", side_effect=Exception("fail")):
            with patch("time.sleep"):
                tickers = _fetch_ticker_data()
                assert tickers == []
