"""
Comprehensive unit tests for app/epaper_service.py.
Mocks ALL external HTTP requests. Tests scraping, caching, insights, and chat.
"""
import json
import os
import threading
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from unittest.mock import patch, MagicMock, PropertyMock

import pytest


# ═══════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def clear_caches():
    """Clear module-level caches before each test."""
    from app import epaper_service as svc
    with svc._cache_lock:
        svc._articles_cache.clear()
        svc._insights_cache.clear()
    yield
    with svc._cache_lock:
        svc._articles_cache.clear()
        svc._insights_cache.clear()


def _make_rss_xml(items):
    """Build a minimal RSS XML string."""
    rss = ET.Element("rss")
    channel = ET.SubElement(rss, "channel")
    for item_data in items:
        item = ET.SubElement(channel, "item")
        for k, v in item_data.items():
            el = ET.SubElement(item, k)
            el.text = v
    return ET.tostring(rss, encoding="unicode")


def _mock_response(status=200, text="", content=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.content = content if content is not None else text.encode("utf-8")
    return resp


# ═══════════════════════════════════════════════════════════
#  BUSINESS LINE SCRAPING
# ═══════════════════════════════════════════════════════════

class TestFetchSectionArticles:
    def test_successful_scrape(self):
        from app.epaper_service import _fetch_section_articles
        html = """
        <html><body>
        <h2><a href="/markets/stock-markets/article12345678.ece">Sensex rallies 500 points on FII buying</a></h2>
        <div><p>Market summary for the day with detailed analysis</p></div>
        <h3><a href="/markets/stock-markets/article87654321.ece">Nifty closes above 22000 mark today</a></h3>
        </body></html>
        """
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=1)
                assert len(articles) == 2
                assert articles[0]["section"] == "Markets"
                assert "Sensex" in articles[0]["title"]

    def test_non_200_response_stops(self):
        from app.epaper_service import _fetch_section_articles
        with patch("app.epaper_service.requests.get", return_value=_mock_response(404)):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=2)
                assert articles == []

    def test_network_error(self):
        from app.epaper_service import _fetch_section_articles
        with patch("app.epaper_service.requests.get", side_effect=Exception("Network error")):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=1)
                assert articles == []

    def test_skip_short_titles(self):
        from app.epaper_service import _fetch_section_articles
        html = '<html><body><h2><a href="/article123">Short</a></h2></body></html>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=1)
                assert articles == []

    def test_skip_non_article_links(self):
        from app.epaper_service import _fetch_section_articles
        html = '<html><body><h2><a href="/markets/overview-page">This is a very long title for a non-article page</a></h2></body></html>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=1)
                assert articles == []

    def test_deduplication_across_pages(self):
        from app.epaper_service import _fetch_section_articles
        html = '<html><body><h2><a href="/article12345678.ece">Sensex rallies 500 points on buying</a></h2></body></html>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            with patch("app.epaper_service.time.sleep"):
                articles = _fetch_section_articles("markets", "Markets", max_pages=3)
                # After first page, same URL should be deduplicated
                assert len(articles) == 1


class TestFetchBLRssArticles:
    def test_successful_rss(self):
        from app.epaper_service import _fetch_bl_rss_articles
        today = date.today().strftime("%a, %d %b %Y %H:%M:%S %z")
        rss = _make_rss_xml([
            {"title": "Sensex rallies 500 points on FII buying today", "link": "https://bl.com/article123",
             "description": "<p>Market is up</p>", "pubDate": today},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_bl_rss_articles("markets", "Markets", lookback_days=7)
            assert len(articles) == 1
            assert articles[0]["source"] == "Business Line"

    def test_rss_non_200(self):
        from app.epaper_service import _fetch_bl_rss_articles
        with patch("app.epaper_service.requests.get", return_value=_mock_response(500)):
            articles = _fetch_bl_rss_articles("markets", "Markets")
            assert articles == []

    def test_rss_error(self):
        from app.epaper_service import _fetch_bl_rss_articles
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            articles = _fetch_bl_rss_articles("markets", "Markets")
            assert articles == []

    def test_rss_skips_old_articles(self):
        from app.epaper_service import _fetch_bl_rss_articles
        old_date = (date.today() - timedelta(days=30)).strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss = _make_rss_xml([
            {"title": "Sensex rallies 500 points old article here", "link": "https://bl.com/article456",
             "pubDate": old_date},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_bl_rss_articles("markets", "Markets", lookback_days=7)
            assert articles == []

    def test_rss_no_article_link(self):
        from app.epaper_service import _fetch_bl_rss_articles
        rss = _make_rss_xml([
            {"title": "Sensex rallies 500 points on FII buying today", "link": "https://bl.com/overview-page"},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_bl_rss_articles("markets", "Markets")
            assert articles == []


class TestFetchArticleBody:
    def test_fetch_body_success(self):
        from app.epaper_service import _fetch_article_body
        html = '<div class="contentbody"><p>This is a substantial paragraph with lots of content here.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_article_body("https://bl.com/article123")
            assert "substantial" in body

    def test_fetch_body_non_200(self):
        from app.epaper_service import _fetch_article_body
        with patch("app.epaper_service.requests.get", return_value=_mock_response(404)):
            body = _fetch_article_body("https://bl.com/article123")
            assert body == ""

    def test_fetch_body_error(self):
        from app.epaper_service import _fetch_article_body
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            body = _fetch_article_body("https://bl.com/article123")
            assert body == ""

    def test_fetch_body_fallback_selectors(self):
        from app.epaper_service import _fetch_article_body
        html = '<div class="paywall"><p>Paywalled content with substantial length here.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_article_body("https://bl.com/article123")
            assert "Paywalled" in body


class TestFetchTHRssArticles:
    def test_successful_th_rss(self):
        from app.epaper_service import _fetch_th_rss_articles
        today = date.today().strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss = _make_rss_xml([
            {"title": "RBI keeps repo rate unchanged for a long time", "link": "https://thehindu.com/article123",
             "description": "<p>Policy details</p>", "pubDate": today},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_th_rss_articles("business/markets", "TH-Markets")
            assert len(articles) == 1
            assert articles[0]["source"] == "The Hindu"

    def test_th_rss_non_200(self):
        from app.epaper_service import _fetch_th_rss_articles
        with patch("app.epaper_service.requests.get", return_value=_mock_response(403)):
            articles = _fetch_th_rss_articles("business", "TH-Business")
            assert articles == []

    def test_th_rss_error(self):
        from app.epaper_service import _fetch_th_rss_articles
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            articles = _fetch_th_rss_articles("business", "TH-Business")
            assert articles == []


class TestFetchTHArticleBody:
    def test_success(self):
        from app.epaper_service import _fetch_th_article_body
        html = '<div class="articlebodycontent"><p>Article body content with detailed info here for the reader.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_th_article_body("https://thehindu.com/article123")
            assert "detailed" in body

    def test_non_200(self):
        from app.epaper_service import _fetch_th_article_body
        with patch("app.epaper_service.requests.get", return_value=_mock_response(500)):
            body = _fetch_th_article_body("https://thehindu.com/article123")
            assert body == ""

    def test_fallback_content_body_id(self):
        from app.epaper_service import _fetch_th_article_body
        html = '<div id="content-body-14123"><p>Article body from content-body selector with enough text.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_th_article_body("https://thehindu.com/article123")
            assert "content-body" in body

    def test_error(self):
        from app.epaper_service import _fetch_th_article_body
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            body = _fetch_th_article_body("https://thehindu.com/article123")
            assert body == ""


class TestFetchGNRssArticles:
    def test_success(self):
        from app.epaper_service import _fetch_gn_rss_articles
        today = date.today().strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss = _make_rss_xml([
            {"title": "Indian stock market Sensex Nifty rally news - Economic Times",
             "link": "https://news.google.com/redirect...",
             "pubDate": today, "source": "Economic Times",
             "description": "<p>Market update from ET</p>"},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_gn_rss_articles("stock+market", "GN-Markets")
            assert len(articles) >= 1

    def test_skips_bl_source(self):
        from app.epaper_service import _fetch_gn_rss_articles
        today = date.today().strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss_xml = """<rss><channel><item>
            <title>Market news from business line source</title>
            <link>https://news.google.com/redirect</link>
            <source>The Hindu Business Line</source>
            <pubDate>{}</pubDate>
        </item></channel></rss>""".format(today)
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss_xml)):
            articles = _fetch_gn_rss_articles("stock+market", "GN-Markets")
            assert articles == []

    def test_non_200(self):
        from app.epaper_service import _fetch_gn_rss_articles
        with patch("app.epaper_service.requests.get", return_value=_mock_response(500)):
            articles = _fetch_gn_rss_articles("query", "GN-Test")
            assert articles == []

    def test_error(self):
        from app.epaper_service import _fetch_gn_rss_articles
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            articles = _fetch_gn_rss_articles("query", "GN-Test")
            assert articles == []


class TestFetchGNArticleBody:
    def test_success(self):
        from app.epaper_service import _fetch_gn_article_body
        html = '<div itemprop="articleBody"><p>Article content with substantial text for parsing here.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_gn_article_body("https://example.com/article")
            assert "substantial" in body

    def test_non_200(self):
        from app.epaper_service import _fetch_gn_article_body
        with patch("app.epaper_service.requests.get", return_value=_mock_response(404)):
            body = _fetch_gn_article_body("https://example.com/article")
            assert body == ""

    def test_fallback_selectors(self):
        from app.epaper_service import _fetch_gn_article_body
        html = '<div class="story-content"><p>Story content with substantial text enough for extraction.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_gn_article_body("https://example.com/article")
            assert "Story" in body

    def test_error(self):
        from app.epaper_service import _fetch_gn_article_body
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            body = _fetch_gn_article_body("https://example.com/article")
            assert body == ""


class TestFetchMCRssArticles:
    def test_success(self):
        from app.epaper_service import _fetch_mc_rss_articles
        today = date.today().strftime("%a, %d %b %Y %H:%M:%S +0000")
        rss = _make_rss_xml([
            {"title": "Sensex Today Live: Market opens higher on global cues",
             "link": "https://moneycontrol.com/article123",
             "pubDate": today, "description": "<p>Markets update</p>"},
        ])
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, rss)):
            articles = _fetch_mc_rss_articles("https://mc.com/rss/test.xml", "MC-Test")
            assert len(articles) == 1
            assert articles[0]["source"] == "Moneycontrol"

    def test_non_200(self):
        from app.epaper_service import _fetch_mc_rss_articles
        with patch("app.epaper_service.requests.get", return_value=_mock_response(500)):
            articles = _fetch_mc_rss_articles("https://mc.com/rss/test.xml", "MC-Test")
            assert articles == []

    def test_error(self):
        from app.epaper_service import _fetch_mc_rss_articles
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            articles = _fetch_mc_rss_articles("https://mc.com/rss/test.xml", "MC-Test")
            assert articles == []


class TestFetchMCArticleBody:
    def test_success(self):
        from app.epaper_service import _fetch_mc_article_body
        html = '<div class="content_wrapper"><p>Moneycontrol article content with detailed analysis here.</p></div>'
        with patch("app.epaper_service.requests.get", return_value=_mock_response(200, html)):
            body = _fetch_mc_article_body("https://mc.com/article123")
            assert "Moneycontrol" in body

    def test_non_200(self):
        from app.epaper_service import _fetch_mc_article_body
        with patch("app.epaper_service.requests.get", return_value=_mock_response(404)):
            body = _fetch_mc_article_body("https://mc.com/article123")
            assert body == ""

    def test_error(self):
        from app.epaper_service import _fetch_mc_article_body
        with patch("app.epaper_service.requests.get", side_effect=Exception("fail")):
            body = _fetch_mc_article_body("https://mc.com/article123")
            assert body == ""


# ═══════════════════════════════════════════════════════════
#  FETCH TODAYS ARTICLES
# ═══════════════════════════════════════════════════════════

class TestFetchTodaysArticles:
    def test_returns_cached(self):
        from app import epaper_service as svc
        today = date.today().isoformat()
        cache_key = f"{today}_d7"
        cached = [{"title": "Cached Article", "url": "https://cached.com"}]
        with svc._cache_lock:
            svc._articles_cache[cache_key] = cached
        result = svc.fetch_todays_articles()
        assert result == cached

    def test_force_refresh_bypasses_cache(self):
        from app import epaper_service as svc
        today = date.today().isoformat()
        cache_key = f"{today}_d7"
        with svc._cache_lock:
            svc._articles_cache[cache_key] = [{"title": "Old"}]
        with patch.object(svc, "_fetch_bl_rss_articles", return_value=[]):
            with patch.object(svc, "_fetch_section_articles", return_value=[]):
                with patch.object(svc, "_fetch_th_rss_articles", return_value=[]):
                    with patch.object(svc, "_fetch_mc_rss_articles", return_value=[]):
                        with patch.object(svc, "_fetch_gn_rss_articles", return_value=[]):
                            with patch.object(svc, "_fetch_article_body", return_value=""):
                                with patch("app.epaper_service.time.sleep"):
                                    result = svc.fetch_todays_articles(force_refresh=True)
                                    assert result != [{"title": "Old"}]


# ═══════════════════════════════════════════════════════════
#  AI ANALYSIS
# ═══════════════════════════════════════════════════════════

class TestCallClaude:
    def test_no_api_key(self):
        from app.epaper_service import _call_claude
        with patch("app.epaper_service._ANTHROPIC_API_KEY", ""):
            result = _call_claude("system", "user")
            assert result == ""

    def test_successful_call(self):
        from app.epaper_service import _call_claude
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"text": "AI response here"}]}
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", return_value=mock_resp):
                result = _call_claude("system", "user")
                assert result == "AI response here"

    def test_api_error(self):
        from app.epaper_service import _call_claude
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Server error"
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", return_value=mock_resp):
                result = _call_claude("system", "user")
                assert result == ""

    def test_exception(self):
        from app.epaper_service import _call_claude
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", side_effect=Exception("timeout")):
                result = _call_claude("system", "user")
                assert result == ""


class TestGenerateInsights:
    def test_cached_insights(self):
        from app import epaper_service as svc
        today = date.today().isoformat()
        cached_insights = [{"headline": "Cached insight"}]
        with svc._cache_lock:
            svc._insights_cache[today] = cached_insights
        result = svc.generate_insights([], [])
        assert result == cached_insights

    def test_no_api_key_fallback(self):
        from app import epaper_service as svc
        with patch.object(svc, "_ANTHROPIC_API_KEY", ""):
            result = svc.generate_insights([], ["RELIANCE"])
            assert isinstance(result, list)

    def test_with_ai_response(self):
        from app import epaper_service as svc
        ai_response = json.dumps([
            {"headline": "Test insight", "detail": "Details", "stocks_affected": ["TCS"],
             "sectors": ["IT"], "sentiment": "positive", "action": "buy", "urgency": "high",
             "article_indices": [1]}
        ])
        articles = [{"title": "TCS wins big order", "section": "IT", "url": "https://test.com",
                      "summary": "Big order", "body": "Content", "source": "Business Line"}]
        with patch.object(svc, "_ANTHROPIC_API_KEY", "test-key"):
            with patch.object(svc, "_call_claude", return_value=ai_response):
                result = svc.generate_insights(articles, ["TCS"])
                assert len(result) == 1
                assert result[0]["headline"] == "Test insight"

    def test_invalid_json_falls_back(self):
        from app import epaper_service as svc
        with patch.object(svc, "_ANTHROPIC_API_KEY", "test-key"):
            with patch.object(svc, "_call_claude", return_value="not json at all"):
                result = svc.generate_insights([], [])
                assert isinstance(result, list)


class TestKeywordInsights:
    def test_matches_portfolio_stocks(self):
        from app.epaper_service import _keyword_insights
        articles = [
            {"title": "RELIANCE Industries announces mega expansion plan today",
             "summary": "Reliance to invest Rs 75000 cr in new projects",
             "body": "RELIANCE GROWTH SURGE", "section": "Markets", "url": "https://test.com"},
        ]
        result = _keyword_insights(articles, ["RELIANCE"])
        assert len(result) >= 1
        assert "RELIANCE" in result[0]["stocks_affected"]

    def test_short_symbol_word_boundary(self):
        from app.epaper_service import _keyword_insights
        articles = [
            {"title": "OIL INDIA Ltd shares SURGE on crude oil prices rally",
             "summary": "", "body": "", "section": "Markets", "url": "https://test.com"},
        ]
        result = _keyword_insights(articles, ["OIL"])
        # OIL is a common word, but "OIL INDIA" should match
        matched = [i for i in result if "OIL" in i.get("stocks_affected", [])]
        assert len(matched) >= 1

    def test_macro_articles(self):
        from app.epaper_service import _keyword_insights
        articles = [
            {"title": "SENSEX crashes 1000 points on global selloff in markets",
             "summary": "", "body": "", "section": "Markets", "url": "https://test.com"},
        ]
        result = _keyword_insights(articles, [])
        assert len(result) >= 1

    def test_max_20_insights(self):
        from app.epaper_service import _keyword_insights
        articles = [
            {"title": f"RELIANCE news article number {i} with long enough title",
             "summary": "", "body": "RELIANCE SURGE", "section": "Markets", "url": f"https://test.com/{i}"}
            for i in range(30)
        ]
        result = _keyword_insights(articles, ["RELIANCE"])
        assert len(result) <= 20


# ═══════════════════════════════════════════════════════════
#  CHAT
# ═══════════════════════════════════════════════════════════

class TestChat:
    def test_no_api_key(self):
        from app.epaper_service import chat
        with patch("app.epaper_service._ANTHROPIC_API_KEY", ""):
            result = chat("hello", [], [])
            assert "API key" in result

    def test_successful_chat(self):
        from app.epaper_service import chat
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"text": "Market analysis response"}]}
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", return_value=mock_resp):
                result = chat("What's happening?", [], ["RELIANCE"])
                assert "Market analysis" in result

    def test_chat_with_history(self):
        from app.epaper_service import chat
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"content": [{"text": "Follow-up response"}]}
        history = [
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer"},
        ]
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", return_value=mock_resp):
                result = chat("Follow-up", [], [], history)
                assert result == "Follow-up response"

    def test_chat_api_error(self):
        from app.epaper_service import chat
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", return_value=mock_resp):
                result = chat("hello", [], [])
                assert "API error" in result

    def test_chat_exception(self):
        from app.epaper_service import chat
        with patch("app.epaper_service._ANTHROPIC_API_KEY", "test-key"):
            with patch("app.epaper_service.requests.post", side_effect=Exception("timeout")):
                result = chat("hello", [], [])
                assert "Error" in result


# ═══════════════════════════════════════════════════════════
#  STATUS
# ═══════════════════════════════════════════════════════════

class TestStatus:
    def test_has_api_key_true(self):
        from app import epaper_service as svc
        with patch.object(svc, "_ANTHROPIC_API_KEY", "test-key"):
            assert svc.has_api_key() is True

    def test_has_api_key_false(self):
        from app import epaper_service as svc
        with patch.object(svc, "_ANTHROPIC_API_KEY", ""):
            assert svc.has_api_key() is False

    def test_get_status(self):
        from app import epaper_service as svc
        status = svc.get_status()
        assert "has_api_key" in status
        assert "articles_cached" in status
        assert "articles_count" in status
        assert "insights_cached" in status
