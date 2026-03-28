"""
Tests for the /api/advisor/analysis-pdf endpoint.

Validates:
- PDF generation with time-organized directory structure (DD-MM-YY/HH_MMhrs.pdf)
- Custom output_path support in generate_briefing_pdf
- Drive sync is attempted after PDF creation
- Proper error handling for empty markdown
"""
import os
import re
from unittest.mock import patch


SAMPLE_MARKDOWN = """> Sources: 10 BL, 5 TH, 3 GN | 2026-03-17 10:00 IST

## Market Overview
- **GIFT Nifty**: 23,400 (+0.5%) — gap-up signal
- **Sensex**: 75,000 (+1.0%). **Nifty**: 23,400 (+0.8%)

## Actionable Stock Ideas
| Stock | Signal | Action | Source | Detail |
|-------|--------|--------|--------|--------|
| ONGC | BULLISH | ADD | BL | Crude windfall |
| TCS | BEARISH | WATCH | BL | AI disruption |

## Key Takeaway
- ADD ONGC below Rs.280. Cash 15-20%.
"""


class TestAnalysisPdfEndpoint:
    """Tests for POST /api/advisor/analysis-pdf."""

    def test_generates_pdf_with_time_directory(self, app_client):
        """PDF is saved to dumps/temp/analysis/DD-MM-YY/HH_MMhrs.pdf."""
        with patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert "filename" in data
        assert data["filename"].endswith("hrs.pdf")
        assert "/temp/analysis/" in data["path"]
        assert os.path.exists(data["path"])
        # Cleanup
        os.remove(data["path"])

    def test_pdf_file_is_valid(self, app_client):
        """Generated PDF file has content and starts with PDF header."""
        with patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        path = resp.json()["path"]
        assert os.path.getsize(path) > 0
        with open(path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"
        os.remove(path)

    def test_drive_sync_flag_present(self, app_client):
        """Response includes drive_synced flag (Google Drive desktop sync handles upload)."""
        resp = app_client.post(
            "/api/advisor/analysis-pdf",
            json={"markdown": SAMPLE_MARKDOWN},
        )

        assert resp.status_code == 200
        assert resp.json()["drive_synced"] is True
        # Cleanup
        os.remove(resp.json()["path"])

    def test_empty_markdown_returns_error(self, app_client):
        """Empty markdown returns error response."""
        resp = app_client.post(
            "/api/advisor/analysis-pdf",
            json={"markdown": ""},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_filename_format(self, app_client):
        """Filename follows HH_MMhrs.pdf pattern."""
        with patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        filename = resp.json()["filename"]
        assert re.match(r"\d{2}_\d{2}hrs\.pdf$", filename)
        os.remove(resp.json()["path"])


class TestBriefingPdfOutputPath:
    """Tests for the output_path parameter in generate_briefing_pdf."""

    def test_custom_output_path(self, tmp_path):
        """With output_path, PDF is saved to the specified location."""
        from app.briefing_pdf import generate_briefing_pdf
        custom = str(tmp_path / "custom" / "my_briefing.pdf")
        path = generate_briefing_pdf("## Test\n- bullet", output_path=custom)

        assert path == custom
        assert os.path.exists(custom)

    def test_custom_path_creates_directories(self, tmp_path):
        """output_path auto-creates parent directories."""
        from app.briefing_pdf import generate_briefing_pdf
        deep_path = str(tmp_path / "a" / "b" / "c" / "test.pdf")
        path = generate_briefing_pdf("## Test\n- data", output_path=deep_path)

        assert os.path.exists(deep_path)
