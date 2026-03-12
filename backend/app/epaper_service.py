"""
Business Line article scraper + AI-powered portfolio advisor.

Scrapes articles from thehindubusinessline.com key sections,
analyzes them using Claude API, and provides personalized insights
based on the user's portfolio holdings.
"""
import os
import re
import json
import time
import threading
from datetime import datetime, date
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(_ENV_PATH)

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
_BL_BASE = "https://www.thehindubusinessline.com"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Sections to scrape (most relevant for investors)
_SECTIONS = [
    ("markets", "Markets"),
    ("markets/stock-markets", "Stock Markets"),
    ("portfolio", "Portfolio"),
    ("money-and-banking", "Money & Banking"),
    ("economy", "Economy"),
    ("companies", "Companies"),
]

# Cache
_articles_cache: Dict[str, list] = {}  # date_str → [articles]
_insights_cache: Dict[str, list] = {}  # date_str → [insights]
_cache_lock = threading.Lock()


# ═══════════════════════════════════════════════════════════
#  ARTICLE SCRAPING
# ═══════════════════════════════════════════════════════════

def _fetch_section_articles(section_path: str, section_name: str) -> List[dict]:
    """Scrape article headlines + summaries from a BL section page."""
    url = f"{_BL_BASE}/{section_path}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[EPaper] Section {section_name} failed: {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")

        articles = []
        seen_urls = set()
        for tag in soup.find_all(["h2", "h3"]):
            a = tag.find("a", href=True)
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a["href"]
            if not title or len(title) < 15 or "/article" not in href:
                continue
            # Make absolute URL
            if href.startswith("/"):
                href = f"{_BL_BASE}{href}"
            if href in seen_urls:
                continue
            seen_urls.add(href)

            # Try to get summary from nearby <p> or sibling
            summary = ""
            parent = tag.parent
            if parent:
                p = parent.find("p")
                if p:
                    summary = p.get_text(strip=True)[:200]

            articles.append({
                "title": title,
                "summary": summary,
                "section": section_name,
                "url": href,
            })
        return articles
    except Exception as e:
        print(f"[EPaper] Error scraping {section_name}: {e}")
        return []


def _fetch_article_body(url: str) -> str:
    """Fetch full article text from a BL article URL."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"[EPaper] Body fetch HTTP {resp.status_code}: {url[-50:]}")
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")

        # BL article body — primary container is div.contentbody#ControlPara
        body_parts = []
        el = soup.find("div", class_="contentbody")
        if not el:
            el = soup.find("div", id="ControlPara")
        if not el:
            # Fallback to other selectors
            for selector in ["div.paywall", "div.article-body", "article"]:
                tag_name = selector.split(".")[0] if "." in selector else selector
                class_name = selector.split(".")[1] if "." in selector else None
                el = soup.find(tag_name, class_=class_name) if class_name else soup.find(tag_name)
                if el:
                    break
        if el:
            for p in el.find_all("p"):
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    body_parts.append(text)

        return "\n\n".join(body_parts)[:3000]  # Cap at 3000 chars per article
    except Exception as e:
        print(f"[EPaper] Error fetching article body: {e}")
        return ""


def fetch_todays_articles(force_refresh: bool = False) -> List[dict]:
    """Fetch all articles from key BL sections. Cached per day."""
    today = date.today().isoformat()

    with _cache_lock:
        if not force_refresh and today in _articles_cache:
            return _articles_cache[today]

    print(f"[EPaper] Scraping Business Line articles for {today}...")
    all_articles = []
    seen_urls = set()

    for section_path, section_name in _SECTIONS:
        articles = _fetch_section_articles(section_path, section_name)
        for art in articles:
            if art["url"] not in seen_urls:
                seen_urls.add(art["url"])
                all_articles.append(art)
        time.sleep(0.5)  # Rate limit

    print(f"[EPaper] Scraped {len(all_articles)} articles from {len(_SECTIONS)} sections")

    # Fetch full body for all articles
    bodies_found = 0
    for i, art in enumerate(all_articles):
        body = _fetch_article_body(art["url"])
        art["body"] = body
        if body:
            bodies_found += 1
        if (i + 1) % 20 == 0:
            print(f"[EPaper] Fetched body for {i+1}/{len(all_articles)} articles ({bodies_found} with content)...")
        time.sleep(0.5)  # Generous delay to avoid rate limiting
    print(f"[EPaper] Total articles with body: {bodies_found}/{len(all_articles)}")

    with _cache_lock:
        _articles_cache[today] = all_articles

    return all_articles


# ═══════════════════════════════════════════════════════════
#  AI ANALYSIS
# ═══════════════════════════════════════════════════════════

def _call_claude(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    """Call Claude API for analysis."""
    if not _ANTHROPIC_API_KEY:
        return ""
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": _ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["content"][0]["text"]
        else:
            print(f"[EPaper] Claude API error: {resp.status_code} {resp.text[:200]}")
            return ""
    except Exception as e:
        print(f"[EPaper] Claude API call failed: {e}")
        return ""


def generate_insights(articles: List[dict], portfolio_symbols: List[str]) -> List[dict]:
    """Use Claude to analyze articles and generate portfolio-relevant insights."""
    today = date.today().isoformat()
    with _cache_lock:
        if today in _insights_cache:
            return _insights_cache[today]

    if not _ANTHROPIC_API_KEY:
        # Fallback: keyword-based matching without AI
        return _keyword_insights(articles, portfolio_symbols)

    # Build article summaries for Claude
    article_texts = []
    for i, art in enumerate(articles[:40]):
        text = f"[{i+1}] [{art['section']}] {art['title']}"
        if art.get("summary"):
            text += f"\n{art['summary']}"
        if art.get("body"):
            text += f"\n{art['body'][:500]}"
        article_texts.append(text)

    articles_block = "\n\n".join(article_texts)
    portfolio_str = ", ".join(portfolio_symbols) if portfolio_symbols else "No holdings data"

    system_prompt = """You are an expert Indian financial advisor analyzing today's Business Line newspaper.
Your job is to extract ACTIONABLE insights for an investor. Focus on:

1. **Direct stock impacts**: Any news about specific companies — investments, earnings, orders, regulatory changes, mergers, management changes
2. **Sector impacts**: News affecting entire sectors (IT, pharma, banking, infra, etc.)
3. **Market outlook**: Overall market direction signals, FII/DII flows, global cues
4. **Mutual fund / Fixed deposit**: Rate changes, NAV impacts, new fund launches
5. **Macro factors**: RBI policy, inflation, crude oil, rupee movement, geopolitical risks

For EACH insight, provide:
- A clear actionable headline
- Which stocks/sectors are affected
- Whether it's POSITIVE, NEGATIVE, or NEUTRAL
- What action the investor should consider (buy/sell/hold/watch)
- Urgency: HIGH (act today), MEDIUM (this week), LOW (monitor)

Return as JSON array of objects with keys: headline, detail, stocks_affected (array), sectors (array), sentiment (positive/negative/neutral), action (buy/sell/hold/watch/avoid), urgency (high/medium/low), article_indices (array of source article numbers)"""

    user_msg = f"""Analyze these Business Line articles from today ({today}).

USER'S PORTFOLIO HOLDINGS: {portfolio_str}
(Prioritize insights about these stocks, but also flag important opportunities and risks outside the portfolio)

ARTICLES:
{articles_block}

Return ONLY a JSON array. Prioritize the most actionable insights first. Include 10-20 insights."""

    response = _call_claude(system_prompt, user_msg)
    if not response:
        return _keyword_insights(articles, portfolio_symbols)

    # Parse JSON from response
    try:
        # Extract JSON array from response (handle markdown code blocks)
        json_match = re.search(r"\[[\s\S]*\]", response)
        if json_match:
            insights = json.loads(json_match.group())
        else:
            insights = json.loads(response)

        # Attach source article URLs
        for insight in insights:
            insight["sources"] = []
            for idx in insight.get("article_indices", []):
                if 1 <= idx <= len(articles):
                    art = articles[idx - 1]
                    insight["sources"].append({"title": art["title"], "url": art["url"]})

        with _cache_lock:
            _insights_cache[today] = insights
        print(f"[EPaper] Generated {len(insights)} AI insights")
        return insights
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[EPaper] Failed to parse Claude response: {e}")
        return _keyword_insights(articles, portfolio_symbols)


def _keyword_insights(articles: List[dict], portfolio_symbols: List[str]) -> List[dict]:
    """Fallback: Simple keyword-based article matching against portfolio."""
    insights = []
    symbols_upper = set(s.upper() for s in portfolio_symbols)
    # Short symbols (<=3 chars) need word-boundary matching to avoid false positives
    # e.g. "OIL" shouldn't match "oil prices" but should match "OIL India"
    _short_syms = {s for s in symbols_upper if len(s) <= 4}
    _long_syms = symbols_upper - _short_syms

    for art in articles:
        text = f"{art['title']} {art.get('summary', '')} {art.get('body', '')}".upper()
        matched_stocks = []
        for s in _long_syms:
            if s in text:
                matched_stocks.append(s)
        for s in _short_syms:
            # Word-boundary match for short symbols
            if re.search(rf'\b{re.escape(s)}\b', text):
                # Extra check: must appear near company-related context
                # Skip if the symbol is a common English word in the article context
                common_words = {"OIL", "GAS", "SUN", "MAX", "YES", "CAN", "BIG", "NEW", "ALL", "ONE"}
                if s in common_words:
                    # Only match if preceded/followed by company indicators
                    if not re.search(rf'\b{re.escape(s)}\s+(INDIA|LTD|LIMITED|CORP|SHARES?|STOCK)', text):
                        continue
                matched_stocks.append(s)

        if matched_stocks:
            # Determine basic sentiment from keywords
            pos_words = ["SURGE", "JUMP", "RALLY", "GAIN", "UP", "RISE", "BULLISH", "GROWTH", "PROFIT", "ORDER", "INVEST"]
            neg_words = ["FALL", "DROP", "CRASH", "LOSS", "BEARISH", "DECLINE", "SELL-OFF", "SLUMP", "CUT", "RISK"]

            pos_count = sum(1 for w in pos_words if w in text)
            neg_count = sum(1 for w in neg_words if w in text)
            sentiment = "positive" if pos_count > neg_count else "negative" if neg_count > pos_count else "neutral"

            insights.append({
                "headline": art["title"],
                "detail": art.get("summary", ""),
                "stocks_affected": matched_stocks,
                "sectors": [art["section"]],
                "sentiment": sentiment,
                "action": "watch",
                "urgency": "medium",
                "sources": [{"title": art["title"], "url": art["url"]}],
            })

    # Also include top market/macro articles
    for art in articles[:10]:
        text = art["title"].upper()
        if any(kw in text for kw in ["SENSEX", "NIFTY", "RBI", "CRUDE", "RUPEE", "FII", "MARKET"]):
            if not any(i["headline"] == art["title"] for i in insights):
                insights.append({
                    "headline": art["title"],
                    "detail": art.get("summary", ""),
                    "stocks_affected": [],
                    "sectors": [art["section"]],
                    "sentiment": "neutral",
                    "action": "watch",
                    "urgency": "medium",
                    "sources": [{"title": art["title"], "url": art["url"]}],
                })

    return insights[:20]


# ═══════════════════════════════════════════════════════════
#  CHAT
# ═══════════════════════════════════════════════════════════

def chat(message: str, articles: List[dict], portfolio_symbols: List[str],
         history: List[dict] = None) -> str:
    """Chat about today's articles with portfolio context."""
    if not _ANTHROPIC_API_KEY:
        return ("I need an Anthropic API key to provide AI-powered analysis. "
                "Please add ANTHROPIC_API_KEY to your .env file.")

    # Build context
    article_summaries = []
    for i, art in enumerate(articles[:30]):
        text = f"[{i+1}] [{art['section']}] {art['title']}"
        if art.get("body"):
            text += f"\n{art['body'][:300]}"
        elif art.get("summary"):
            text += f"\n{art['summary']}"
        article_summaries.append(text)

    context = "\n\n".join(article_summaries)
    portfolio_str = ", ".join(portfolio_symbols) if portfolio_symbols else "No portfolio data"

    system_prompt = f"""You are an expert Indian financial advisor. You have access to today's Business Line newspaper articles and the user's stock portfolio.

USER'S PORTFOLIO: {portfolio_str}

TODAY'S BUSINESS LINE ARTICLES:
{context}

Guidelines:
- Give specific, actionable advice based on the articles
- Reference specific article numbers when citing sources
- Flag any news that directly affects the user's holdings
- Warn about risks and highlight opportunities
- Be concise but thorough — don't miss critical information
- If asked about a specific stock, check if any article mentions it
- For buy/sell recommendations, always mention the risk level
- Use INR for all currency references"""

    messages = []
    if history:
        for h in history[-10:]:  # Last 10 messages for context
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": _ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2048,
                "system": system_prompt,
                "messages": messages,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            return resp.json()["content"][0]["text"]
        else:
            return f"API error: {resp.status_code} — {resp.text[:200]}"
    except Exception as e:
        return f"Error calling AI: {str(e)}"


# ═══════════════════════════════════════════════════════════
#  STATUS
# ═══════════════════════════════════════════════════════════

def has_api_key() -> bool:
    return bool(_ANTHROPIC_API_KEY)


def get_status() -> dict:
    today = date.today().isoformat()
    return {
        "has_api_key": has_api_key(),
        "articles_cached": today in _articles_cache,
        "articles_count": len(_articles_cache.get(today, [])),
        "insights_cached": today in _insights_cache,
        "insights_count": len(_insights_cache.get(today, [])),
    }
