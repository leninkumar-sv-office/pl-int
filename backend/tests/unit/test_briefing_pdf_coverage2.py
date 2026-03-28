"""
Additional coverage tests for briefing_pdf.py — targeting remaining uncovered lines.
Covers: _draw_dashboard with period data, _extract_actions, _draw_action_summary,
_parse_sector_bullets, _draw_sector_bars, _render_table edge cases,
_match_table_layout, _calc_col_widths, _find_colored_cols, _set_row_fill,
generate_briefing_pdf with all element types.
"""
import os
from unittest.mock import patch, MagicMock
import pytest


class TestDrawDashboard:
    def test_dashboard_with_period_data(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_dashboard
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        metrics = [
            ("SENSEX", "76,034", -1.08, 2.5, -3.0),
            ("NIFTY", "23,639", 0.5, None, None),
            ("GOLD", "5,154", 0.0, 0.0, 0.0),
        ]
        _draw_dashboard(pdf, metrics)
        output = pdf.output(dest="S")
        assert len(output) > 0

    def test_dashboard_no_metrics(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_dashboard
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _draw_dashboard(pdf, [])
        output = pdf.output(dest="S")
        assert len(output) > 0

    def test_dashboard_all_positive(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_dashboard
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        metrics = [
            ("TEST", "100.50", 2.5, 3.0, 5.0),
        ]
        _draw_dashboard(pdf, metrics)
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestExtractActions:
    def test_basic_action_extraction(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Stock | Signal | Action |",
            "|---|---|---|",
            "| RELIANCE | Bullish | BUY |",
            "| TCS | Bearish | SELL |",
            "| INFY | Neutral | WATCH |",
        ]
        result = _extract_actions(lines)
        assert "BUY" in result
        assert "SELL" in result
        assert "WATCH" in result

    def test_action_with_value_column(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Stock | Value | Signal | Action | Why |",
            "|---|---|---|---|---|",
            "| **RELIANCE** | Rs.2500 | Bullish | TRIM | Profit booking |",
        ]
        result = _extract_actions(lines)
        assert "TRIM" in result

    def test_no_action_column(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Stock | Signal |",
            "|---|---|",
            "| RELIANCE | Bullish |",
        ]
        result = _extract_actions(lines)
        assert result == {}

    def test_non_table_lines_reset(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "Regular text here",
            "| Stock | Action |",
            "|---|---|",
            "| RELIANCE | BUY |",
            "Not a table line",
            "| Stock | Action |",
            "|---|---|",
            "| TCS | SELL |",
        ]
        result = _extract_actions(lines)
        assert "BUY" in result
        assert "SELL" in result

    def test_dedup_same_stock(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Stock | Action |",
            "|---|---|",
            "| RELIANCE | BUY |",
            "| RELIANCE | BUY |",
        ]
        result = _extract_actions(lines)
        assert len(result.get("BUY", [])) == 1

    def test_action_col_out_of_range(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Stock | Action |",
            "|---|---|",
            "| RELIANCE |",  # Only 1 cell, action_col=1 out of range
        ]
        result = _extract_actions(lines)
        # Should not crash

    def test_detail_column(self):
        from app.briefing_pdf import _extract_actions
        lines = [
            "| Held Stock | Signal | Action | Detail |",
            "|---|---|---|---|",
            "| RELIANCE | Bullish | ADD | Strong fundamentals |",
        ]
        result = _extract_actions(lines)
        assert "ADD" in result


class TestDrawActionSummary:
    def test_draw_action_summary(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_action_summary
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        lines = [
            "| Stock | Action |",
            "|---|---|",
            "| RELIANCE | TRIM |",
            "| TCS | BUY |",
            "| INFY | SELL |",
            "| HDFC | WATCH |",
            "| SBI | EXIT |",
            "| AXIS | ADD |",
        ]
        _draw_action_summary(pdf, lines)
        output = pdf.output(dest="S")
        assert len(output) > 0

    def test_draw_no_actions(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_action_summary
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _draw_action_summary(pdf, ["no table here"])
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestParseSectorBullets:
    def test_known_directions(self):
        from app.briefing_pdf import _parse_sector_bullets
        lines = [
            "- Banking: BULLISH. Strong growth expected",
            "- IT: BEARISH. Weak demand",
            "- Pharma: MIXED. Depends on approvals",
            "- Auto: FLAT. No change",
            "- Energy: CRISIS. Major disruption",
            "- Infra: POSITIVE. Government spending",
            "- FMCG: STABLE. Steady demand",
            "- Metals: NEGATIVE. Price decline",
        ]
        result = _parse_sector_bullets(lines)
        assert len(result) == 8
        assert result[0][1] == "BULLISH"
        assert result[1][1] == "BEARISH"

    def test_unmatched_line(self):
        from app.briefing_pdf import _parse_sector_bullets
        lines = ["- Some random text without a colon direction marker"]
        result = _parse_sector_bullets(lines)
        assert len(result) == 1
        assert result[0][1] == "MIXED"  # default


class TestDrawSectorBars:
    def test_draw_sector_bars(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _draw_sector_bars
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        lines = [
            "- Banking: BULLISH. Strong growth",
            "- IT: BEARISH. Weak demand",
        ]
        _draw_sector_bars(pdf, lines)
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestMatchTableLayout:
    def test_known_layout(self):
        from app.briefing_pdf import _match_table_layout
        header = ["Stock", "Signal", "Action", "Source", "Detail"]
        result = _match_table_layout(header, 5)
        assert result is not None
        assert len(result) == 5

    def test_unknown_layout(self):
        from app.briefing_pdf import _match_table_layout
        header = ["Unknown1", "Unknown2", "Unknown3"]
        result = _match_table_layout(header, 3)
        assert result is None


class TestCalcColWidths:
    def test_basic(self):
        from app.briefing_pdf import _calc_col_widths
        header = ["Stock", "Price"]
        data = [["RELIANCE", "2500.00"], ["TCS", "3600.00"]]
        widths = _calc_col_widths(header, data, 190, 2)
        assert len(widths) == 2
        assert abs(sum(widths) - 190) < 1

    def test_zero_cols(self):
        from app.briefing_pdf import _calc_col_widths
        result = _calc_col_widths([], [], 190, 0)
        assert result == []

    def test_equal_length_cols(self):
        from app.briefing_pdf import _calc_col_widths
        header = ["A", "B", "C"]
        data = [["x", "x", "x"]]
        widths = _calc_col_widths(header, data, 190, 3)
        assert len(widths) == 3


class TestFindColoredCols:
    def test_signal_col(self):
        from app.briefing_pdf import _find_colored_cols
        header = ["Stock", "Signal", "Action", "Detail"]
        cols = _find_colored_cols(header)
        assert 1 in cols  # Signal
        assert 2 in cols  # Action

    def test_no_signal_col(self):
        from app.briefing_pdf import _find_colored_cols
        header = ["Stock", "Price", "Volume"]
        cols = _find_colored_cols(header)
        assert len(cols) == 0


class TestSetRowFill:
    def test_action_row(self):
        from app.briefing_pdf import BriefingPDF, _set_row_fill
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _set_row_fill(pdf, True, None, False)

    def test_row_tint(self):
        from app.briefing_pdf import BriefingPDF, _set_row_fill
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _set_row_fill(pdf, False, (255, 240, 235), False)

    def test_alt_fill(self):
        from app.briefing_pdf import BriefingPDF, _set_row_fill
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _set_row_fill(pdf, False, None, True)

    def test_no_fill(self):
        from app.briefing_pdf import BriefingPDF, _set_row_fill
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _set_row_fill(pdf, False, None, False)


class TestRenderTable:
    def test_render_with_signal_column(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _render_table
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        rows = [
            ["Stock", "Signal", "Action", "Source", "Detail"],
            ["RELIANCE", "Bullish", "BUY", "BL", "Strong momentum"],
            ["TCS", "Bearish", "SELL", "TH", "Weak outlook"],
        ]
        _render_table(pdf, rows)
        output = pdf.output(dest="S")
        assert len(output) > 0

    def test_render_empty_table(self):
        from app.briefing_pdf import BriefingPDF, _render_table
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _render_table(pdf, [])

    def test_render_with_action_today(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _render_table
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        rows = [
            ["Stock", "Signal", "Action", "Detail"],
            ["RELIANCE [ACTION TODAY]", "Bullish", "TRIM", "Take profits"],
        ]
        _render_table(pdf, rows)
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestGenerateBriefingPdfComprehensive:
    def test_with_h3_subsection(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = "## Section\n\n### Subsection\n\nContent here."
        output_path = str(tmp_path / "h3.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_sector_impact_bullets(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = (
            "## Sector Impacts\n\n"
            "- Banking: BULLISH. Strong growth\n"
            "- IT: BEARISH. Weak demand\n"
            "---\n"
        )
        output_path = str(tmp_path / "sector_impacts.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_action_today_bullet(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = (
            "## Recommendations\n\n"
            "- [ACTION TODAY] RELIANCE — take profits now\n"
            "- Normal bullet point\n"
        )
        output_path = str(tmp_path / "action_today.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_key_takeaway_section(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = (
            "## Key Takeaway\n\n"
            "Markets are volatile. Stay cautious.\n"
        )
        output_path = str(tmp_path / "takeaway.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_live_tickers(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        tickers = [
            {"key": "SENSEX", "price": 76034, "change_pct": -1.08,
             "week_change_pct": 2.0, "month_change_pct": -3.0, "unit": ""},
            {"key": "CRUDEOIL", "price": 85.5, "change_pct": 0.5,
             "week_change_pct": 1.0, "month_change_pct": -2.0, "unit": "$/bbl"},
            {"key": "GOLD", "price": 5154, "change_pct": -0.4,
             "week_change_pct": 0.5, "month_change_pct": 3.0, "unit": ""},
        ]
        md = "## Market Overview\n\nContent\n"
        output_path = str(tmp_path / "tickers.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=tickers):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)

    def test_with_multi_column_table_and_wrapping(self, tmp_path):
        from app.briefing_pdf import generate_briefing_pdf
        md = (
            "## Analysis\n\n"
            "| Who | What | How Much | Why It Matters |\n"
            "|---|---|---|---|\n"
            "| RBI | Rate cut | 25 bps | Boosts lending and growth |\n"
            "| FII | Selling | Rs.5000cr | Negative for markets |\n"
        )
        output_path = str(tmp_path / "who_what.pdf")
        with patch("app.briefing_pdf._fetch_ticker_data", return_value=[]):
            filepath = generate_briefing_pdf(md, output_path=output_path)
        assert os.path.exists(filepath)


class TestGetSectionLines:
    def test_basic(self):
        from app.briefing_pdf import _get_section_lines
        lines = [
            "## Market Overview",
            "Line 1",
            "Line 2",
            "## Recommendations",
            "Line 3",
        ]
        result = _get_section_lines(lines, "Market Overview")
        assert result == ["Line 1", "Line 2"]

    def test_section_not_found(self):
        from app.briefing_pdf import _get_section_lines
        lines = ["## Section A", "Content"]
        result = _get_section_lines(lines, "Section B")
        assert result == []

    def test_section_end_with_hr(self):
        from app.briefing_pdf import _get_section_lines
        lines = [
            "## Test Section",
            "Content",
            "---",
            "More stuff",
        ]
        result = _get_section_lines(lines, "Test Section")
        assert result == ["Content"]


class TestFlushSectorBars:
    def test_flush_active(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _flush_sector_bars
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        bullets = ["- IT: BULLISH. Strong growth"]
        _flush_sector_bars(pdf, bullets, True)
        output = pdf.output(dest="S")
        assert len(output) > 0

    def test_flush_inactive(self, tmp_path):
        from app.briefing_pdf import BriefingPDF, _flush_sector_bars
        pdf = BriefingPDF("Test")
        pdf.alias_nb_pages()
        pdf.add_page()
        _flush_sector_bars(pdf, ["- text"], False)
        output = pdf.output(dest="S")
        assert len(output) > 0


class TestBuildDashboardPriceFormatting:
    def test_medium_price_format(self):
        from app.briefing_pdf import _build_dashboard_metrics
        tickers = [
            {"key": "CRUDEOIL", "price": 500.5, "change_pct": 1.0,
             "week_change_pct": 0.5, "month_change_pct": 2.0, "unit": ""},
        ]
        result = _build_dashboard_metrics(tickers, [])
        assert len(result) >= 1
        # Price 500.5 should be formatted with 1 decimal
        assert "500.5" in result[0][1]

    def test_unit_appended(self):
        from app.briefing_pdf import _build_dashboard_metrics
        tickers = [
            {"key": "CRUDEOIL", "price": 85.5, "change_pct": 0.5,
             "unit": "$/bbl", "week_change_pct": None, "month_change_pct": None},
        ]
        result = _build_dashboard_metrics(tickers, [])
        assert len(result) >= 1
        assert "$/bbl" in result[0][1]
