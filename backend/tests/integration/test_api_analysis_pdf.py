"""
Tests for the /api/advisor/analysis-pdf endpoint.

Validates:
- PDF generation with time-organized directory structure (DD-MM-YY/HH_MMhrs.pdf)
- Custom output_path support in generate_briefing_pdf
- Drive sync is attempted after PDF creation
- Proper error handling for empty markdown
"""
import os
from unittest.mock import patch

import pytest


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

    def test_generates_pdf_with_time_directory(self, app_client, auth_token, tmp_path):
        """PDF is saved to dumps/temp/analysis/DD-MM-YY/HH_MMhrs.pdf."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")), \
             patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "path" in data
        assert "filename" in data
        assert data["filename"].endswith("hrs.pdf")
        # Directory structure: .../DD-MM-YY/HH_MMhrs.pdf
        assert "/temp/analysis/" in data["path"]
        assert os.path.exists(data["path"])

    def test_pdf_file_is_valid(self, app_client, auth_token, tmp_path):
        """Generated PDF file has content and starts with PDF header."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")), \
             patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        path = resp.json()["path"]
        assert os.path.getsize(path) > 0
        with open(path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"

    def test_drive_sync_attempted(self, app_client, auth_token, tmp_path):
        """Drive upload_file is called after PDF generation."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")), \
             patch("app.drive_service.upload_file") as mock_upload:
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        assert resp.status_code == 200
        assert resp.json()["drive_synced"] is True
        mock_upload.assert_called_once()
        call_args = mock_upload.call_args
        # First arg is the filepath, subfolder contains analysis dir
        assert "analysis" in str(call_args)

    def test_drive_sync_failure_returns_false(self, app_client, auth_token, tmp_path):
        """If Drive sync fails, drive_synced is False but PDF still generated."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")), \
             patch("app.drive_service.upload_file", side_effect=Exception("Drive down")):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["drive_synced"] is False
        assert os.path.exists(data["path"])

    def test_empty_markdown_returns_error(self, app_client, auth_token):
        """Empty markdown returns error response."""
        resp = app_client.post(
            "/api/advisor/analysis-pdf",
            json={"markdown": ""},
        )
        assert resp.status_code == 200
        assert "error" in resp.json()

    def test_filename_format(self, app_client, auth_token, tmp_path):
        """Filename follows HH_MMhrs.pdf pattern."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")), \
             patch("app.drive_service.upload_file", return_value=None):
            resp = app_client.post(
                "/api/advisor/analysis-pdf",
                json={"markdown": SAMPLE_MARKDOWN},
            )

        import re
        filename = resp.json()["filename"]
        assert re.match(r"\d{2}_\d{2}hrs\.pdf$", filename)


class TestBriefingPdfOutputPath:
    """Tests for the output_path parameter in generate_briefing_pdf."""

    def test_default_path_unchanged(self, tmp_path):
        """Without output_path, PDF goes to default _DUMPS_DIR."""
        with patch("app.briefing_pdf._DUMPS_DIR", str(tmp_path / "summary")):
            from app.briefing_pdf import generate_briefing_pdf
            path = generate_briefing_pdf("## Test\n- bullet")

        assert "/summary/" in path
        assert path.endswith(".pdf")
        assert os.path.exists(path)

    def test_custom_output_path(self, tmp_path):
        """With output_path, PDF is saved to the specified location."""
        custom = str(tmp_path / "custom" / "my_briefing.pdf")
        from app.briefing_pdf import generate_briefing_pdf
        path = generate_briefing_pdf("## Test\n- bullet", output_path=custom)

        assert path == custom
        assert os.path.exists(custom)

    def test_custom_path_creates_directories(self, tmp_path):
        """output_path auto-creates parent directories."""
        deep_path = str(tmp_path / "a" / "b" / "c" / "test.pdf")
        from app.briefing_pdf import generate_briefing_pdf
        path = generate_briefing_pdf("## Test\n- data", output_path=deep_path)

        assert os.path.exists(deep_path)
