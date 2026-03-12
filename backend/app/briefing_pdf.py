"""
Generate a styled PDF market briefing from scraped articles + portfolio data.
Output: backend/dumps/summary/YYYY-MM-DD_HHMMSS.pdf
"""
import os
import re
from datetime import datetime
from fpdf import FPDF

_DUMPS_DIR = os.path.join(os.path.dirname(__file__), "..", "dumps", "summary")

# --- Color constants ---
_BLUE = (20, 60, 120)
_WHITE = (255, 255, 255)
_BLACK = (0, 0, 0)
_GREY = (100, 100, 100)
_LIGHT_GREY = (200, 200, 200)

# Signal → (background, text color) for table badges
_SIGNAL_STYLES = {
    "bullish":    ((220, 245, 220), (0, 100, 0)),
    "buy":        ((220, 245, 220), (0, 100, 0)),
    "positive":   ((220, 245, 220), (0, 100, 0)),
    "accumulate": ((210, 240, 210), (0, 100, 0)),
    "bearish":    ((255, 220, 220), (160, 0, 0)),
    "sell":       ((255, 220, 220), (160, 0, 0)),
    "book profit":((255, 230, 210), (160, 60, 0)),
    "underweight":((255, 220, 220), (160, 0, 0)),
    "buy put":    ((255, 220, 220), (160, 0, 0)),
    "neutral":    ((255, 245, 210), (140, 100, 0)),
    "watch":      ((255, 245, 210), (140, 100, 0)),
    "mixed":      ((255, 245, 210), (140, 100, 0)),
    "flat":       ((235, 235, 235), (80, 80, 80)),
    "stable":     ((220, 235, 250), (0, 60, 120)),
    "crisis":     ((255, 200, 200), (160, 0, 0)),
    "action":     ((255, 235, 200), (180, 80, 0)),
    "add":        ((210, 240, 210), (0, 100, 0)),
    "hold":       ((220, 235, 250), (0, 60, 120)),
    "trim":       ((255, 235, 210), (180, 80, 0)),
    "exit":       ((255, 210, 210), (180, 0, 0)),
    "avoid":      ((255, 220, 220), (160, 0, 0)),
}

# Sector direction → (bar color, bar width ratio 0-1)
_SECTOR_BAR_CFG = {
    "CRISIS":   ((200, 40, 40),   1.0),
    "BEARISH":  ((220, 80, 60),   0.75),
    "NEGATIVE": ((220, 100, 80),  0.6),
    "MIXED":    ((200, 170, 50),  0.5),
    "FLAT":     ((150, 150, 150), 0.35),
    "STABLE":   ((80, 140, 200),  0.45),
    "POSITIVE": ((40, 160, 40),   0.7),
    "BULLISH":  ((30, 140, 30),   0.9),
}

# Known table layouts: header keyword → fixed column widths
_TABLE_LAYOUTS = {
    # Stock | Signal | Action | Source | Detail
    ("stock", "signal", "action", "source", "detail"): [26, 28, 18, 14, 104],
    # Stock | Signal | Source | Detail (legacy 4-col)
    ("stock", "signal", "source", "detail"): [28, 32, 14, 116],
    # WHO | WHAT | HOW MUCH | WHY IT MATTERS
    ("who", "what", "how much", "why it matters"): [36, 44, 36, 74],
    # WHAT | WHO | HOW BAD | ACTION
    ("what", "who", "how bad", "action"): [50, 32, 54, 54],
    # Item | Detail
    ("item", "detail"): [35, 155],
}


def _get_signal_style(signal_text):
    """Return (bg_color, text_color) for a signal string."""
    lower = signal_text.lower().strip("[] ")
    for key, (bg, tc) in _SIGNAL_STYLES.items():
        if key in lower:
            return bg, tc
    return (235, 235, 235), (80, 80, 80)


class BriefingPDF(FPDF):
    def __init__(self, title_text: str):
        super().__init__()
        self._title_text = title_text
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*_GREY)
        self.cell(0, 8, self._title_text, align="L")
        self.ln(4)
        self.set_draw_color(*_LIGHT_GREY)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def _clean(text: str) -> str:
    """Strip markdown markers and replace non-latin1 chars."""
    text = text.replace("**[ACTION TODAY]**", "[ACTION TODAY]")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = text.replace("\u2014", "-")
    text = text.replace("\u2013", "-")
    text = text.replace("\u2018", "'")
    text = text.replace("\u2019", "'")
    text = text.replace("\u201c", '"')
    text = text.replace("\u201d", '"')
    text = text.replace("\u2026", "...")
    text = text.replace("\u20b9", "Rs.")
    text = text.replace("\u2192", "->")
    text = text.replace("\u2022", "-")
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    return text


# ─── Market Dashboard ────────────────────────────────────────────

def _extract_metrics(lines):
    """Extract key market numbers from Market Overview + Macro text."""
    text = " ".join(lines)
    metrics = []

    # Sensex: "plunged 1.08% to 76,034" or "rose 0.5% to 77,000"
    m = re.search(r'Sensex.*?(\d+\.?\d*)\s*%\s*to\s*([\d,]+)', text)
    if m:
        chg = float(m.group(1))
        val = m.group(2)
        # Check direction from verb
        pre = text[:text.find(m.group(1))]
        if re.search(r'(plunged|fell|dropped|declined|lost|slipped|down)', pre, re.IGNORECASE):
            chg = -chg
        metrics.append(("SENSEX", val, chg))

    # Nifty50: "dropped 0.95% to 23,639"
    m = re.search(r'Nifty\s*50.*?(\d+\.?\d*)\s*%\s*to\s*([\d,]+)', text)
    if m:
        chg = float(m.group(1))
        val = m.group(2)
        pre = text[:text.find(m.group(1))]
        if re.search(r'(plunged|fell|dropped|declined|lost|slipped|down)', pre, re.IGNORECASE):
            chg = -chg
        metrics.append(("NIFTY 50", val, chg))

    # Brent crude: "$100/bbl (+9%)"
    m = re.search(r'[Bb]rent[^$]*?\$([\d.]+)', text)
    if m:
        chg_m = re.search(r'[Bb]rent[^)]*?\(([+-]?\d+\.?\d*)%\)', text)
        chg = float(chg_m.group(1)) if chg_m else 0
        metrics.append(("BRENT", "$" + m.group(1), chg))

    # Gold: "$5,154/oz (-0.4%)"
    m = re.search(r'Gold.*?\$([\d,]+)', text)
    if m:
        chg_m = re.search(r'Gold[^)]*?\(([+-]?\d+\.?\d*)%\)', text)
        chg = float(chg_m.group(1)) if chg_m else 0
        metrics.append(("GOLD", "$" + m.group(1), chg))

    # Rupee: "settled at 92.17" or just first number
    m = re.search(r'Rupee.*?settled.*?(\d+\.\d+)', text)
    if not m:
        m = re.search(r'Rupee.*?(\d+\.\d+)', text)
    if m:
        metrics.append(("INR/USD", m.group(1), -1))

    return metrics


def _fetch_ticker_data():
    """Fetch live ticker data from the market-ticker API."""
    try:
        import urllib.request
        import json
        req = urllib.request.urlopen("http://localhost:8000/api/market-ticker", timeout=5)
        data = json.loads(req.read())
        return data.get("tickers", [])
    except Exception:
        return []


def _build_dashboard_metrics(tickers, text_metrics):
    """Build dashboard metrics from API tickers, falling back to text extraction."""
    if not tickers:
        # Fallback: use text-extracted metrics (1D only)
        return [(l, v, c, None, None) for l, v, c in text_metrics]

    # Map ticker keys to display
    key_map = {
        "SENSEX": "SENSEX",
        "NIFTY50": "NIFTY 50",
        "GIFTNIFTY": "GIFT NIFTY",
        "CRUDEOIL": "CRUDE OIL",
        "GOLD": "GOLD",
        "USDINR": "INR/USD",
    }
    desired = ["SENSEX", "NIFTY50", "GIFTNIFTY", "CRUDEOIL", "GOLD", "USDINR"]
    result = []
    for key in desired:
        t = next((t for t in tickers if t["key"] == key), None)
        if not t:
            continue
        label = key_map.get(key, key)
        price = t.get("price", 0)
        unit = t.get("unit", "")
        # Format value
        if price >= 10000:
            val = f"{price:,.0f}"
        elif price >= 100:
            val = f"{price:,.1f}"
        else:
            val = f"{price:.2f}"
        if unit and "Rs" not in unit:
            val = val + " " + _clean(unit)
        d1 = t.get("change_pct", 0) or 0
        w1 = t.get("week_change_pct") or 0
        m1 = t.get("month_change_pct") or 0
        result.append((label, val, d1, w1, m1))
    return result


def _draw_dashboard(pdf, metrics):
    """Render colored metric cards with 1D/1W/1M change percentages."""
    if not metrics:
        return
    n = len(metrics)
    gap = 2
    box_w = (190 - gap * (n - 1)) / n
    has_periods = any(m[3] is not None for m in metrics)
    box_h = 32 if has_periods else 22
    y = pdf.get_y()

    def _chg_color(v):
        if v > 0:
            return (0, 120, 0)
        elif v < 0:
            return (180, 0, 0)
        return (100, 100, 100)

    def _fmt_chg(v):
        if v > 0:
            return f"+{v:.1f}%"
        return f"{v:.1f}%"

    for i, metric in enumerate(metrics):
        label, value, d1 = metric[0], metric[1], metric[2]
        w1 = metric[3] if len(metric) > 3 else None
        m1 = metric[4] if len(metric) > 4 else None

        x = 10 + i * (box_w + gap)
        border_c = _chg_color(d1)
        bg = (228, 248, 228) if d1 > 0 else (252, 228, 228) if d1 < 0 else (240, 240, 240)

        # Box
        pdf.set_fill_color(*bg)
        pdf.set_draw_color(*border_c)
        pdf.rect(x, y, box_w, box_h, style="DF")
        # Top accent bar
        pdf.set_fill_color(*border_c)
        pdf.rect(x, y, box_w, 2, style="F")

        # Label
        pdf.set_xy(x, y + 3)
        pdf.set_font("Helvetica", "", 5.5)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(box_w, 3.5, label, align="C")

        # Value
        pdf.set_xy(x, y + 6.5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(20, 20, 20)
        pdf.cell(box_w, 6, _clean(value), align="C")

        # 1D change (prominent)
        pdf.set_xy(x, y + 13)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*_chg_color(d1))
        pdf.cell(box_w, 4, _fmt_chg(d1) + " 1D", align="C")

        # 1W and 1M (smaller, below)
        if has_periods and w1 is not None:
            # Divider line
            pdf.set_draw_color(200, 200, 200)
            pdf.line(x + 2, y + 18, x + box_w - 2, y + 18)

            third_w = box_w / 2
            # 1W
            pdf.set_xy(x, y + 19.5)
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(*_chg_color(w1))
            pdf.cell(third_w, 4, _fmt_chg(w1), align="C")
            pdf.set_font("Helvetica", "", 4.5)
            pdf.set_text_color(120, 120, 120)
            pdf.set_xy(x, y + 23)
            pdf.cell(third_w, 3, "1W", align="C")

            # 1M
            pdf.set_xy(x + third_w, y + 19.5)
            pdf.set_font("Helvetica", "", 6)
            pdf.set_text_color(*_chg_color(m1))
            pdf.cell(third_w, 4, _fmt_chg(m1), align="C")
            pdf.set_font("Helvetica", "", 4.5)
            pdf.set_text_color(120, 120, 120)
            pdf.set_xy(x + third_w, y + 23)
            pdf.cell(third_w, 3, "1M", align="C")

    pdf.set_y(y + box_h + 4)
    pdf.set_text_color(*_BLACK)


# ─── Sector Impact Bars ──────────────────────────────────────────

def _parse_sector_bullets(bullet_lines):
    """Parse sector impact bullets into (name, direction, detail)."""
    sectors = []
    for line in bullet_lines:
        text = _clean(line.strip().lstrip("- "))
        m = re.match(
            r'^([^:]+):\s*(CRISIS|BEARISH|POSITIVE|MIXED|FLAT|BULLISH|STABLE|NEGATIVE)'
            r'[^.]*\.?\s*(.*)$',
            text, re.IGNORECASE
        )
        if m:
            sectors.append((m.group(1).strip(), m.group(2).strip().upper(), m.group(3).strip()))
        else:
            sectors.append((text[:35], "MIXED", text[35:]))
    return sectors


def _draw_sector_bars(pdf, bullet_lines):
    """Render horizontal color-coded bars for each sector."""
    sectors = _parse_sector_bullets(bullet_lines)
    if not sectors:
        return

    label_w = 34
    bar_max_w = 55
    row_h = 7.5

    for sector, direction, detail in sectors:
        if pdf.get_y() > 260:
            pdf.add_page()

        y = pdf.get_y()
        color, strength = _SECTOR_BAR_CFG.get(direction, ((150, 150, 150), 0.4))
        bar_w = max(bar_max_w * strength, 18)

        # Sector label
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(40, 40, 40)
        pdf.set_xy(10, y)
        pdf.cell(label_w, row_h, _clean(sector), align="R")

        # Colored bar
        bar_x = 10 + label_w + 2
        bar_y = y + 1.2
        pdf.set_fill_color(*color)
        pdf.rect(bar_x, bar_y, bar_w, row_h - 2.4, style="F")

        # Direction text on bar
        pdf.set_xy(bar_x + 1.5, bar_y - 0.3)
        pdf.set_font("Helvetica", "B", 6)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(bar_w - 3, row_h - 2, direction, align="L")

        # Detail text
        detail_x = bar_x + bar_w + 3
        remaining_w = 200 - detail_x
        if remaining_w > 10 and detail:
            pdf.set_xy(detail_x, y)
            pdf.set_font("Helvetica", "", 6.5)
            pdf.set_text_color(50, 50, 50)
            max_c = int(remaining_w * 2.3)
            d = _clean(detail)
            if len(d) > max_c:
                d = d[:max_c - 2] + ".."
            pdf.cell(remaining_w, row_h, d)

        pdf.set_y(y + row_h + 0.5)

    pdf.ln(2)
    pdf.set_text_color(*_BLACK)


# ─── Table rendering ─────────────────────────────────────────────

def _match_table_layout(header, n_cols):
    """Match header against known layouts for optimal column widths."""
    h_lower = tuple(h.lower().strip() for h in header)
    for pattern, widths in _TABLE_LAYOUTS.items():
        if len(pattern) == n_cols and all(p in h_lower[i] for i, p in enumerate(pattern) if i < len(h_lower)):
            return widths
    return None


def _calc_col_widths(header, data, page_w, n_cols):
    """Proportional column widths based on content length."""
    if n_cols <= 0:
        return []
    max_lens = []
    for j in range(n_cols):
        lengths = [len(header[j]) if j < len(header) else 5]
        for row in data[:15]:
            lengths.append(len(row[j]) if j < len(row) else 5)
        max_lens.append(max(max(lengths), 5))

    total = sum(max_lens)
    if total == 0:
        return [page_w / n_cols] * n_cols

    widths = [max(14, (l / total) * page_w) for l in max_lens]
    scale = page_w / sum(widths)
    return [w * scale for w in widths]


def _find_colored_cols(header):
    """Find indices of columns that should be color-coded (signal, action)."""
    cols = set()
    for j, h in enumerate(header):
        hl = h.lower().strip()
        if "signal" in hl or hl == "action" or hl == "today's signal":
            cols.add(j)
    return cols


def _render_table(pdf, rows):
    """Render a table with smart column widths and color-coded signals."""
    if not rows:
        return

    header = rows[0]
    data = rows[1:]
    n_cols = len(header)
    page_w = 190

    # Try known layout first, fallback to proportional
    col_widths = _match_table_layout(header, n_cols)
    if not col_widths:
        col_widths = _calc_col_widths(header, data, page_w, n_cols)

    colored_cols = _find_colored_cols(header)
    row_h = 5.5

    def _truncate(txt, w, font_style=""):
        """Truncate text to fit within width w using actual font metrics."""
        cur_style = pdf.font_style
        if font_style and font_style != cur_style:
            pdf.set_font("Helvetica", font_style, pdf.font_size_pt)
        if pdf.get_string_width(txt) <= w - 1:
            if font_style and font_style != cur_style:
                pdf.set_font("Helvetica", cur_style, pdf.font_size_pt)
            return txt
        while len(txt) > 3 and pdf.get_string_width(txt + "..") > w - 1:
            txt = txt[:-1]
        if font_style and font_style != cur_style:
            pdf.set_font("Helvetica", cur_style, pdf.font_size_pt)
        return txt + ".."

    def _draw_header():
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(30, 70, 130)
        pdf.set_text_color(255, 255, 255)
        for j in range(n_cols):
            w = col_widths[j]
            txt = _clean(header[j]) if j < len(header) else ""
            txt = _truncate(txt, w, "B")
            pdf.cell(w, 6.5, txt, border=1, fill=True)
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

    _draw_header()

    # Identify the last (widest) column — use multi_cell for wrapping
    last_col = n_cols - 1

    def _calc_row_height(txt, w):
        """Calculate how many lines text will need in multi_cell."""
        if not txt:
            return row_h
        pdf.set_font("Helvetica", "", 7)
        text_w = pdf.get_string_width(txt)
        n_lines = max(1, int(text_w / (w - 2)) + 1)
        return max(row_h, n_lines * 3.5)

    pdf.set_font("Helvetica", "", 7)
    for row_idx, row in enumerate(data):
        if pdf.get_y() > 255:
            pdf.add_page()
            _draw_header()
            pdf.set_font("Helvetica", "", 7)

        alt_fill = row_idx % 2 == 0
        row_text = " ".join(row)
        is_action_row = "[ACTION TODAY]" in row_text

        # Pre-calculate row height based on last column text
        last_txt = _clean(row[last_col]) if last_col < len(row) else ""
        rh = _calc_row_height(last_txt, col_widths[last_col])

        row_y = pdf.get_y()

        for j in range(n_cols):
            w = col_widths[j]
            txt = _clean(row[j]) if j < len(row) else ""

            if j in colored_cols:
                bg, tc = _get_signal_style(txt)
                pdf.set_fill_color(*bg)
                pdf.set_text_color(*tc)
                pdf.set_font("Helvetica", "B", 6.5)
                txt = _truncate(txt, w, "B")
                pdf.set_xy(pdf.get_x(), row_y)
                pdf.cell(w, rh, txt, border=1, fill=True)
                pdf.set_font("Helvetica", "", 7)
                pdf.set_text_color(*_BLACK)
            elif j == last_col:
                # Last column: wrap text with multi_cell
                if is_action_row:
                    pdf.set_fill_color(255, 245, 230)
                elif alt_fill:
                    pdf.set_fill_color(245, 248, 255)
                else:
                    pdf.set_fill_color(255, 255, 255)
                x_before = pdf.get_x()
                pdf.set_xy(x_before, row_y)
                # Draw border rect first, then text
                pdf.rect(x_before, row_y, w, rh, style="D")
                # Fill
                fill_c = pdf.fill_color
                pdf.rect(x_before + 0.2, row_y + 0.2, w - 0.4, rh - 0.4, style="F")
                pdf.set_xy(x_before + 0.5, row_y + 0.5)
                pdf.multi_cell(w - 1, 3.5, txt)
                pdf.set_x(pdf.l_margin)
            else:
                if is_action_row:
                    pdf.set_fill_color(255, 245, 230)
                elif alt_fill:
                    pdf.set_fill_color(245, 248, 255)
                else:
                    pdf.set_fill_color(255, 255, 255)
                txt = _truncate(txt, w)
                pdf.set_xy(pdf.get_x(), row_y)
                pdf.cell(w, rh, txt, border=1, fill=True if is_action_row else alt_fill)

        pdf.set_y(row_y + rh)


# ─── Main generator ──────────────────────────────────────────────

def generate_briefing_pdf(markdown_text: str) -> str:
    """Parse a markdown briefing and generate a styled PDF."""
    os.makedirs(_DUMPS_DIR, exist_ok=True)
    now = datetime.now()
    filename = now.strftime("%Y-%m-%d_%H%M%S") + ".pdf"
    filepath = os.path.join(_DUMPS_DIR, filename)

    date_str = now.strftime("%B %d, %Y %I:%M %p")
    pdf = BriefingPDF(f"Market Briefing - {date_str}")
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_BLUE)
    pdf.cell(0, 12, "Daily Market Briefing", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*_GREY)
    pdf.cell(0, 6, date_str, ln=True, align="C")
    pdf.ln(4)

    lines = markdown_text.split("\n")

    # ── Dashboard: prefer live API data, fallback to text extraction ──
    tickers = _fetch_ticker_data()
    overview_lines = _get_section_lines(lines, "Market Overview")
    macro_lines = _get_section_lines(lines, "Macro")
    text_metrics = _extract_metrics(overview_lines + macro_lines)
    dashboard = _build_dashboard_metrics(tickers, text_metrics)
    if dashboard:
        _draw_dashboard(pdf, dashboard)

    # ── Track current section for special rendering ──
    current_section = ""
    in_sector_impacts = False
    sector_bullets = []

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Empty line — don't reset sector mode (bullets may follow after blanks)
        if not line.strip():
            pdf.ln(2)
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            text = _clean(line[2:])
            pdf.set_fill_color(240, 245, 255)
            pdf.set_draw_color(50, 80, 140)
            y0 = pdf.get_y()
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(50, 80, 140)
            pdf.multi_cell(0, 6, text, fill=True)
            # Left accent bar on blockquote
            pdf.set_fill_color(50, 80, 140)
            pdf.rect(10, y0, 1.5, pdf.get_y() - y0, style="F")
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(*_BLACK)
            pdf.ln(3)
            i += 1
            continue

        # H2 section header
        if line.startswith("## "):
            _flush_sector_bars(pdf, sector_bullets, in_sector_impacts)
            sector_bullets = []

            text = _clean(line[3:])
            current_section = text
            in_sector_impacts = "Sector Impacts" in text

            pdf.ln(4)
            pdf.set_fill_color(*_BLUE)
            pdf.set_text_color(*_WHITE)
            pdf.set_font("Helvetica", "B", 13)
            pdf.cell(0, 9, f"  {text}", ln=True, fill=True)
            pdf.set_text_color(*_BLACK)
            pdf.ln(3)
            i += 1
            continue

        # H3 subsection
        if line.startswith("### "):
            text = _clean(line[4:])
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(*_BLUE)
            pdf.cell(0, 7, text, ln=True)
            pdf.set_draw_color(*_BLUE)
            pdf.line(10, pdf.get_y(), 120, pdf.get_y())
            pdf.set_text_color(*_BLACK)
            pdf.ln(3)
            i += 1
            continue

        # Horizontal rule
        if line.strip() == "---":
            _flush_sector_bars(pdf, sector_bullets, in_sector_impacts)
            sector_bullets = []
            in_sector_impacts = False
            pdf.set_draw_color(*_LIGHT_GREY)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(4)
            i += 1
            continue

        # Table
        if "|" in line and line.strip().startswith("|"):
            table_lines = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.match(r"^\|[\s\-:|]+\|$", row):
                    cells = [c.strip() for c in row.split("|")[1:-1]]
                    table_lines.append(cells)
                i += 1
            if table_lines:
                _render_table(pdf, table_lines)
                pdf.ln(3)
            continue

        # Bullet point — sector impacts get special bar rendering
        if line.strip().startswith("- "):
            if in_sector_impacts:
                sector_bullets.append(line)
                i += 1
                continue

            text = _clean(line.strip()[2:])
            # Highlight [ACTION TODAY] bullets
            if "[ACTION TODAY]" in text:
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_fill_color(255, 240, 220)
                pdf.set_text_color(180, 80, 0)
                pdf.cell(6, 5.5, "-")
                pdf.multi_cell(0, 5.5, text, fill=True)
                pdf.set_x(pdf.l_margin)
                pdf.set_text_color(*_BLACK)
            else:
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(6, 5, "-")
                pdf.multi_cell(0, 5, text)
                pdf.set_x(pdf.l_margin)
            i += 1
            continue

        # Key Takeaway — render in highlighted callout box
        if "Key Takeaway" in current_section and line.strip():
            text = _clean(line.strip())
            y0 = pdf.get_y()
            # Draw background first across full width
            pdf.set_fill_color(255, 250, 235)
            pdf.set_font("Helvetica", "", 9.5)
            pdf.set_text_color(60, 40, 0)
            # Indent text past accent bar
            pdf.set_x(pdf.l_margin + 4)
            pdf.multi_cell(186, 6, text, fill=True)
            # Left accent bar (gold)
            pdf.set_fill_color(200, 160, 30)
            pdf.rect(10, y0, 2.5, pdf.get_y() - y0, style="F")
            pdf.set_x(pdf.l_margin)
            pdf.set_text_color(*_BLACK)
            pdf.ln(1)
            i += 1
            continue

        # Regular paragraph
        text = _clean(line.strip())
        if text:
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, text)
            pdf.set_x(pdf.l_margin)
        i += 1

    # Flush any remaining sector bars
    _flush_sector_bars(pdf, sector_bullets, in_sector_impacts)

    pdf.output(filepath)
    print(f"[Briefing] PDF saved: {filepath}")
    return filepath


def _get_section_lines(lines, section_name):
    """Extract lines belonging to a ## section."""
    collecting = False
    result = []
    for line in lines:
        if line.strip().startswith("## ") and section_name in line:
            collecting = True
            continue
        elif collecting and (line.strip().startswith("## ") or line.strip() == "---"):
            break
        elif collecting:
            result.append(line)
    return result


def _flush_sector_bars(pdf, bullets, active):
    """Render accumulated sector impact bullets as bars."""
    if active and bullets:
        _draw_sector_bars(pdf, bullets)
