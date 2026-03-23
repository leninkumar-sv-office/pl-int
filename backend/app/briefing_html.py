"""
Generate a styled HTML market briefing from markdown text.
Output: backend/dumps/summary/YYYY-MM-DD_HHMMSS.html
"""
import os
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DUMPS_DIR = os.path.join(os.path.dirname(__file__), "..", "dumps", "summary")

# Signal → CSS class
_SIGNAL_CLASSES = {
    "bullish": "signal-bull", "buy": "signal-bull", "positive": "signal-bull",
    "accumulate": "signal-bull", "add": "signal-bull",
    "bearish": "signal-bear", "sell": "signal-bear", "exit": "signal-bear",
    "book profit": "signal-warn", "underweight": "signal-bear", "buy put": "signal-bear",
    "neutral": "signal-neutral", "watch": "signal-neutral", "mixed": "signal-neutral",
    "hold": "signal-hold", "stable": "signal-hold",
    "trim": "signal-warn", "avoid": "signal-bear",
    "crisis": "signal-bear", "action": "signal-warn",
}

# Sector direction → CSS class
_SECTOR_CLASSES = {
    "CRISIS": "sector-crisis", "BEARISH": "sector-bear", "NEGATIVE": "sector-bear",
    "MIXED": "sector-mixed", "FLAT": "sector-flat",
    "STABLE": "sector-stable", "POSITIVE": "sector-bull", "BULLISH": "sector-bull",
}

_ACTION_CLASSES = {
    "TRIM": "action-warn", "SELL": "action-bear", "EXIT": "action-bear",
    "ADD": "action-bull", "BUY": "action-bull", "WATCH": "action-neutral",
    "HOLD": "action-hold",
}

_CSS = """
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-dim: #8b949e; --text-bright: #f0f6fc;
  --green: #3fb950; --green-bg: rgba(63,185,80,0.12);
  --red: #f85149; --red-bg: rgba(248,81,73,0.12);
  --yellow: #d29922; --yellow-bg: rgba(210,153,34,0.12);
  --blue: #58a6ff; --blue-bg: rgba(88,166,255,0.12);
  --orange: #d18616; --orange-bg: rgba(209,134,22,0.12);
  --grey: #8b949e; --grey-bg: rgba(139,148,158,0.12);
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
  max-width: 1100px; margin: 0 auto; padding: 20px;
}
h1 { font-size: 1.6em; color: var(--text-bright); margin: 24px 0 8px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
h2 { font-size: 1.3em; color: var(--text-bright); margin: 20px 0 8px; }
h3 { font-size: 1.15em; color: var(--blue); margin: 18px 0 8px; }
p { margin: 4px 0; }
blockquote {
  border-left: 3px solid var(--blue); padding: 8px 12px; margin: 8px 0;
  background: var(--surface); color: var(--text-dim); font-size: 0.9em;
}
ul, ol { padding-left: 20px; margin: 4px 0; }
li { margin: 3px 0; }
strong { color: var(--text-bright); }
hr { border: none; border-top: 1px solid var(--border); margin: 16px 0; }

/* Dashboard cards */
.dashboard { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.metric-card {
  flex: 1; min-width: 140px; max-width: 200px;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 10px 12px; text-align: center;
  border-top: 3px solid var(--grey);
}
.metric-card.up { border-top-color: var(--green); }
.metric-card.down { border-top-color: var(--red); }
.metric-card .label { font-size: 0.7em; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; }
.metric-card .value { font-size: 1.3em; font-weight: 700; color: var(--text-bright); margin: 2px 0; }
.metric-card .change { font-size: 0.85em; font-weight: 600; }
.metric-card .change.up { color: var(--green); }
.metric-card .change.down { color: var(--red); }
.metric-card .periods { display: flex; gap: 8px; justify-content: center; margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); font-size: 0.75em; }
.metric-card .periods span { color: var(--text-dim); }
.metric-card .periods .val.up { color: var(--green); }
.metric-card .periods .val.down { color: var(--red); }

/* Tables */
table {
  width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 0.85em;
}
thead th {
  background: #1c2536; color: var(--blue); padding: 8px 10px;
  text-align: left; font-weight: 600; border-bottom: 2px solid var(--border);
  white-space: nowrap;
}
tbody td {
  padding: 7px 10px; border-bottom: 1px solid var(--border);
  vertical-align: top;
}
tbody tr:hover { background: rgba(88,166,255,0.04); }

/* Signal/action badges */
.badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 0.8em; font-weight: 600; white-space: nowrap;
}
.signal-bull { background: var(--green-bg); color: var(--green); }
.signal-bear { background: var(--red-bg); color: var(--red); }
.signal-neutral { background: var(--yellow-bg); color: var(--yellow); }
.signal-hold { background: var(--blue-bg); color: var(--blue); }
.signal-warn { background: var(--orange-bg); color: var(--orange); }

/* Action cards */
.action-cards { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
.action-card {
  border-radius: 8px; padding: 8px 12px; min-width: 120px;
}
.action-card .card-label { font-weight: 700; font-size: 0.85em; margin-bottom: 4px; }
.action-card .card-item { font-size: 0.8em; color: var(--text); opacity: 0.9; }
.action-bull { background: var(--green-bg); border: 1px solid rgba(63,185,80,0.3); }
.action-bull .card-label { color: var(--green); }
.action-bear { background: var(--red-bg); border: 1px solid rgba(248,81,73,0.3); }
.action-bear .card-label { color: var(--red); }
.action-warn { background: var(--orange-bg); border: 1px solid rgba(209,134,22,0.3); }
.action-warn .card-label { color: var(--orange); }
.action-neutral { background: var(--yellow-bg); border: 1px solid rgba(210,153,34,0.3); }
.action-neutral .card-label { color: var(--yellow); }
.action-hold { background: var(--blue-bg); border: 1px solid rgba(88,166,255,0.3); }
.action-hold .card-label { color: var(--blue); }

/* Sector bars */
.sector-bar { display: flex; align-items: center; margin: 3px 0; }
.sector-bar .sector-name { width: 140px; text-align: right; padding-right: 10px; font-size: 0.85em; font-weight: 600; color: var(--text-dim); }
.sector-bar .bar { height: 24px; border-radius: 4px; display: flex; align-items: center; padding: 0 8px; font-size: 0.75em; font-weight: 700; color: #fff; min-width: 60px; }
.sector-bar .detail { font-size: 0.8em; color: var(--text-dim); padding-left: 10px; flex: 1; }
.sector-crisis .bar { background: #c82828; }
.sector-bear .bar { background: #dc5040; }
.sector-mixed .bar { background: #c8aa32; }
.sector-flat .bar { background: #969696; }
.sector-stable .bar { background: #5090c8; }
.sector-bull .bar { background: #1ea028; }

/* Responsive */
@media (max-width: 600px) {
  body { padding: 10px; }
  .dashboard { flex-direction: column; }
  .metric-card { max-width: 100%; }
  table { font-size: 0.78em; }
  thead th, tbody td { padding: 5px 6px; }
}
"""


def _esc(text):
    """HTML-escape text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _md_inline(text):
    """Convert inline markdown to HTML (bold, italic, code)."""
    text = _esc(text)
    text = re.sub(r'\*\*\[ACTION TODAY\]\*\*', '<strong style="color:var(--orange)">[ACTION TODAY]</strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
    return text


def _get_signal_class(text):
    """Return CSS class for a signal/action text."""
    lower = text.lower().strip("[] ")
    for key, cls in _SIGNAL_CLASSES.items():
        if key in lower:
            return cls
    return "signal-neutral"


def _get_action_class(text):
    """Return CSS class for an action card."""
    upper = text.upper().strip()
    return _ACTION_CLASSES.get(upper, "action-neutral")


def _is_signal_col(header_text):
    """Check if a column should have signal badges."""
    h = header_text.lower().strip()
    return "signal" in h or h == "action" or h == "today's signal" or h == "1d"


def _render_cell(text, is_signal_col=False):
    """Render a table cell, optionally as a badge."""
    if is_signal_col and text.strip():
        cls = _get_signal_class(text)
        return f'<span class="badge {cls}">{_esc(text.strip())}</span>'
    return _md_inline(text)


def _extract_actions(lines):
    """Extract action items from table rows for action cards."""
    actions = {}
    in_table = False
    action_col = -1
    stock_col = 0
    value_col = -1

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            in_table = False
            continue
        if re.match(r"^\|[\s\-:|]+\|$", line):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if not in_table:
            lower_cells = [c.lower() for c in cells]
            for j, h in enumerate(lower_cells):
                if h == "action":
                    action_col = j
                elif "stock" in h or h == "held stock":
                    stock_col = j
                elif "value" in h:
                    value_col = j
            in_table = True
            continue
        if action_col < 0 or action_col >= len(cells):
            continue
        action = re.sub(r'\*\*', '', cells[action_col]).strip().upper()
        stock = re.sub(r'\*\*|\[ACTION TODAY\]', '', cells[stock_col]).strip() if stock_col < len(cells) else ""
        if action in _ACTION_CLASSES and stock:
            val = cells[value_col].strip() if value_col >= 0 and value_col < len(cells) else ""
            label = f"{stock} ({val})" if val else stock
            actions.setdefault(action, []).append(label)

    # Dedup
    deduped = {}
    for act, items in actions.items():
        seen = {}
        for label in items:
            base = label.split("(")[0].strip()[:15]
            if base not in seen or "(" in label:
                seen[base] = label
        deduped[act] = list(seen.values())
    return deduped


def _render_action_cards(actions):
    """Render action summary cards HTML."""
    if not actions:
        return ""
    order = ["EXIT", "TRIM", "SELL", "ADD", "BUY", "HOLD", "WATCH"]
    html = '<h3>Today\'s Actions</h3>\n<div class="action-cards">\n'
    for act in order:
        if act not in actions:
            continue
        cls = _get_action_class(act)
        html += f'<div class="action-card {cls}">\n'
        html += f'  <div class="card-label">{_esc(act)}</div>\n'
        for item in actions[act][:8]:
            html += f'  <div class="card-item">{_esc(item)}</div>\n'
        html += '</div>\n'
    html += '</div>\n'
    return html


def _parse_sector_bullets(lines):
    """Parse sector bullets into (name, direction, detail)."""
    sectors = []
    for line in lines:
        text = line.strip().lstrip("- ")
        # Remove markdown bold
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        m = re.match(
            r'^([^:]+):\s*(CRISIS|BEARISH|POSITIVE|MIXED|FLAT|BULLISH|STABLE|NEGATIVE|OUTPERFORMER|RELATIVE OUTPERFORMER|EMERGING THEME|EMERGING)'
            r'[^.]*\.?\s*(.*)$',
            text, re.IGNORECASE
        )
        if m:
            direction = m.group(2).strip().upper()
            # Normalize
            if direction in ("OUTPERFORMER", "RELATIVE OUTPERFORMER"):
                direction = "BULLISH"
            elif direction in ("EMERGING THEME", "EMERGING"):
                direction = "POSITIVE"
            sectors.append((m.group(1).strip(), direction, m.group(3).strip()))
    return sectors


def _render_sector_bars(lines):
    """Render sector impact bars as HTML."""
    sectors = _parse_sector_bullets(lines)
    if not sectors:
        return ""

    bar_widths = {
        "CRISIS": 100, "BEARISH": 75, "NEGATIVE": 60,
        "MIXED": 50, "FLAT": 35, "STABLE": 45,
        "POSITIVE": 70, "BULLISH": 90,
    }

    html = ""
    for name, direction, detail in sectors:
        cls = _SECTOR_CLASSES.get(direction, "sector-mixed")
        w = bar_widths.get(direction, 50)
        html += f'<div class="sector-bar {cls}">\n'
        html += f'  <div class="sector-name">{_esc(name)}</div>\n'
        html += f'  <div class="bar" style="width:{w}%">{_esc(direction)}</div>\n'
        if detail:
            # Truncate detail for display
            d = detail[:200]
            html += f'  <div class="detail">{_md_inline(d)}</div>\n'
        html += '</div>\n'
    return html


def _fetch_ticker_data():
    """Fetch live ticker data from the market-ticker API."""
    import urllib.request
    import json
    import time
    for attempt in range(3):
        try:
            req = urllib.request.urlopen("http://localhost:9999/api/market-ticker", timeout=8)
            data = json.loads(req.read())
            tickers = data.get("tickers", [])
            if tickers:
                return tickers
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1)
    return []


def _render_dashboard(tickers):
    """Render market dashboard cards from ticker data."""
    if not tickers:
        return ""

    key_map = {
        "SENSEX": "SENSEX", "NIFTY50": "NIFTY 50", "GIFTNIFTY": "GIFT NIFTY",
        "CRUDEOIL": "CRUDE OIL", "GOLD": "GOLD", "USDINR": "INR/USD",
    }
    desired = ["SENSEX", "NIFTY50", "GIFTNIFTY", "CRUDEOIL", "GOLD", "USDINR"]

    html = '<div class="dashboard">\n'
    for key in desired:
        t = next((t for t in tickers if t["key"] == key), None)
        if not t:
            continue
        label = key_map.get(key, key)
        price = t.get("price", 0)
        unit = t.get("unit", "")
        d1 = t.get("change_pct", 0) or 0
        w1 = t.get("week_change_pct") or 0
        m1 = t.get("month_change_pct") or 0

        if price >= 10000:
            val = f"{price:,.0f}"
        elif price >= 100:
            val = f"{price:,.1f}"
        else:
            val = f"{price:.2f}"
        if unit and "₹" not in unit and "Rs" not in unit:
            val += " " + unit

        direction = "up" if d1 > 0 else "down" if d1 < 0 else ""
        d1_str = f"+{d1:.1f}%" if d1 > 0 else f"{d1:.1f}%"
        w1_str = f"+{w1:.1f}%" if w1 > 0 else f"{w1:.1f}%"
        m1_str = f"+{m1:.1f}%" if m1 > 0 else f"{m1:.1f}%"
        w1_cls = "up" if w1 > 0 else "down" if w1 < 0 else ""
        m1_cls = "up" if m1 > 0 else "down" if m1 < 0 else ""

        html += f'<div class="metric-card {direction}">\n'
        html += f'  <div class="label">{_esc(label)}</div>\n'
        html += f'  <div class="value">{_esc(val)}</div>\n'
        html += f'  <div class="change {direction}">{d1_str} 1D</div>\n'
        html += f'  <div class="periods">\n'
        html += f'    <div><span class="val {w1_cls}">{w1_str}</span> <span>1W</span></div>\n'
        html += f'    <div><span class="val {m1_cls}">{m1_str}</span> <span>1M</span></div>\n'
        html += f'  </div>\n'
        html += f'</div>\n'
    html += '</div>\n'
    return html


def generate_briefing_html(markdown_text, output_path=None):
    """Convert markdown briefing to styled HTML file.

    Returns the file path of the generated HTML.
    """
    os.makedirs(_DUMPS_DIR, exist_ok=True)
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

    lines = markdown_text.split("\n")

    # Fetch ticker data for dashboard
    tickers = _fetch_ticker_data()

    # Parse into sections
    sections = []
    current_heading = None
    current_lines = []
    sector_lines = []
    in_sector = False

    for line in lines:
        if line.startswith("### "):
            if current_heading or current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line[4:].strip()
            current_lines = []
            in_sector = "sector" in current_heading.lower()
        else:
            current_lines.append(line)
            if in_sector and line.strip().startswith("- "):
                sector_lines.append(line)
    if current_heading or current_lines:
        sections.append((current_heading, current_lines))

    # Extract actions from all lines
    actions = _extract_actions(lines)

    # Build HTML
    body_html = ""

    # Preamble (blockquote lines before first heading)
    if sections and sections[0][0] is None:
        for line in sections[0][1]:
            stripped = line.strip()
            if stripped.startswith("> "):
                body_html += f"<blockquote>{_md_inline(stripped[2:])}</blockquote>\n"
            elif stripped:
                body_html += f"<p>{_md_inline(stripped)}</p>\n"
        sections = sections[1:]

    # Dashboard right after preamble
    body_html += _render_dashboard(tickers)

    # Action cards right after dashboard
    body_html += _render_action_cards(actions)

    # Render each section
    for heading, content_lines in sections:
        if heading:
            body_html += f"<h3>{_esc(heading)}</h3>\n"

        # Check if section has a table
        table_rows = []
        non_table_lines = []
        in_table = False
        is_sector_section = heading and "sector" in heading.lower()

        for line in content_lines:
            stripped = line.strip()
            if stripped.startswith("|") and "|" in stripped[1:]:
                # Skip separator rows
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    if table_rows:
                        in_table = True
                    continue
                cells = [c.strip() for c in stripped.split("|")[1:-1]]
                table_rows.append(cells)
                in_table = True
            else:
                if in_table and table_rows:
                    # Render accumulated table
                    body_html += _render_table(table_rows)
                    table_rows = []
                    in_table = False
                non_table_lines.append(stripped)

        # Render remaining table
        if table_rows:
            body_html += _render_table(table_rows)

        # Sector bars
        if is_sector_section and sector_lines:
            body_html += _render_sector_bars(sector_lines)
        elif non_table_lines:
            # Render non-table content
            for line in non_table_lines:
                if not line:
                    continue
                if line.startswith("- ") and not is_sector_section:
                    body_html += f"<li>{_md_inline(line[2:])}</li>\n"
                elif line.startswith("> "):
                    body_html += f"<blockquote>{_md_inline(line[2:])}</blockquote>\n"
                elif line.startswith("---"):
                    body_html += "<hr>\n"
                else:
                    body_html += f"<p>{_md_inline(line)}</p>\n"

    now = datetime.now()
    title = f"Market Briefing — {now.strftime('%d %b %Y %H:%M')}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<h1>{_esc(title)}</h1>
{body_html}
<hr>
<p style="text-align:center;color:var(--text-dim);font-size:0.8em;margin-top:16px;">
  Generated {now.strftime('%Y-%m-%d %H:%M IST')} &middot; Portfolio Dashboard
</p>
</body>
</html>"""

    if not output_path:
        stamp = now.strftime("%Y-%m-%d_%H%M%S")
        output_path = os.path.join(_DUMPS_DIR, f"{stamp}.html")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Briefing HTML saved to %s", output_path)
    return output_path


def _render_table(rows):
    """Render a markdown table as HTML."""
    if not rows:
        return ""

    header = rows[0]
    data = rows[1:]
    signal_cols = {j for j, h in enumerate(header) if _is_signal_col(h)}

    html = '<table>\n<thead><tr>\n'
    for h in header:
        html += f'  <th>{_esc(h)}</th>\n'
    html += '</tr></thead>\n<tbody>\n'

    for row in data:
        html += '<tr>\n'
        for j, cell in enumerate(row):
            content = _render_cell(cell, j in signal_cols)
            html += f'  <td>{content}</td>\n'
        # Pad if row has fewer cells
        for _ in range(len(header) - len(row)):
            html += '  <td></td>\n'
        html += '</tr>\n'

    html += '</tbody></table>\n'
    return html
