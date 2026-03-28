"""
Expiry/maturity alert rules for FD, RD, PPF, NPS, SI, and Insurance.

Per-user rules stored in dumps/{email}/{Name}/settings/expiry_rules.json.
Background evaluation checks instruments against rules and sends notifications.
"""
import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

from .config import DUMPS_BASE, get_user_dumps_dir, get_users

# Valid categories and their rule types
RULE_TYPES = {
    "fd": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "rd": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "ppf": [
        {"type": "days_before_maturity", "label": "Days before maturity", "needs_days": True},
        {"type": "on_maturity", "label": "On maturity day", "needs_days": False},
    ],
    "nps": [
        {"type": "contribution_reminder", "label": "Contribution reminder", "needs_days": False},
    ],
    "si": [
        {"type": "days_before_expiry", "label": "Days before expiry", "needs_days": True},
        {"type": "on_expiry", "label": "On expiry day", "needs_days": False},
    ],
    "insurance": [
        {"type": "days_before_expiry", "label": "Days before expiry", "needs_days": True},
        {"type": "on_expiry", "label": "On expiry day", "needs_days": False},
    ],
    "stocks": [
        {"type": "profit_threshold", "label": "Lot profit exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "day_drop_threshold", "label": "1D price drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "week_drop_threshold", "label": "1W price drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "month_drop_threshold", "label": "1M price drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "near_52w_high", "label": "At or crossed 52-week high", "needs_pct": False, "needs_time": True},
        {"type": "near_52w_low", "label": "At or hit 52-week low", "needs_pct": False, "needs_time": True},
    ],
    "mf": [
        {"type": "profit_threshold", "label": "Unit profit exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "day_drop_threshold", "label": "1D NAV drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "week_drop_threshold", "label": "1W NAV drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "month_drop_threshold", "label": "1M NAV drop exceeds %", "needs_pct": True, "needs_time": True},
        {"type": "near_52w_high", "label": "At or crossed 52-week high", "needs_pct": False, "needs_time": True},
        {"type": "near_52w_low", "label": "At or hit 52-week low", "needs_pct": False, "needs_time": True},
    ],
}

# Legacy files for migration
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LEGACY_RULES_FILE = _DATA_DIR / "expiry_rules.json"


# ── Persistence (files on Google Drive mount) ─────────────

def _settings_dir(user_id: str, email: str) -> Path:
    """Get settings dir: dumps/{email}/{Name}/settings/"""
    dumps_dir = get_user_dumps_dir(user_id, email)
    d = dumps_dir / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rules_file(user_id: str, email: str) -> Path:
    return _settings_dir(user_id, email) / "expiry_rules.json"


def _load_rules(email: str, user_id: str) -> list:
    fp = _rules_file(user_id, email)
    try:
        with open(fp) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return _migrate_legacy(email, user_id)


def _save_rules(email: str, user_id: str, rules: list):
    fp = _rules_file(user_id, email)
    with open(fp, "w") as f:
        json.dump(rules, f, indent=2)


def _migrate_legacy(email: str, user_id: str) -> list:
    """Migrate from legacy shared files to per-user file."""
    # Try legacy v2 (dumps/{email}/settings/expiry_rules_{userId}.json)
    legacy_v2 = DUMPS_BASE / email / "settings" / f"expiry_rules_{user_id}.json"
    if legacy_v2.exists():
        try:
            with open(legacy_v2) as f:
                rules = json.load(f)
            if isinstance(rules, list) and rules:
                _save_rules(email, user_id, rules)
                legacy_v2.unlink(missing_ok=True)
                logger.info(f"[ExpiryRules] Migrated {len(rules)} rules from v2 for {user_id}")
                return rules
        except Exception:
            pass

    # Try legacy v1 (data/expiry_rules.json with email:userId keys)
    if _LEGACY_RULES_FILE.exists():
        try:
            with open(_LEGACY_RULES_FILE) as f:
                all_data = json.load(f)
            key = f"{email}:{user_id}"
            rules = all_data.get(key, [])
            if rules:
                _save_rules(email, user_id, rules)
                del all_data[key]
                if all_data:
                    with open(_LEGACY_RULES_FILE, "w") as f:
                        json.dump(all_data, f, indent=2)
                else:
                    _LEGACY_RULES_FILE.unlink(missing_ok=True)
                logger.info(f"[ExpiryRules] Migrated {len(rules)} rules from v1 for {user_id}")
            return rules
        except Exception as e:
            logger.error(f"[ExpiryRules] Legacy migration failed: {e}")

    return []


# ── Public API ───────────────────────────────────────────

def get_rules(email: str, user_id: str, category: str = None) -> List[dict]:
    rules = _load_rules(email, user_id)
    if category:
        rules = [r for r in rules if r.get("category") == category]
    return rules


def save_rule(email: str, user_id: str, rule_data: dict) -> dict:
    rules = _load_rules(email, user_id)
    now = datetime.now().isoformat(timespec="seconds")

    rule_id = rule_data.get("id", "").strip()
    if rule_id:
        for i, r in enumerate(rules):
            if r["id"] == rule_id:
                rules[i] = {**r, **rule_data, "updated_at": now}
                _save_rules(email, user_id, rules)
                return rules[i]

    rule = {
        "id": str(uuid.uuid4())[:8],
        "category": rule_data.get("category", ""),
        "rule_type": rule_data.get("rule_type", ""),
        "days": rule_data.get("days", 30),
        "enabled": rule_data.get("enabled", True),
        "created_at": now,
        "updated_at": now,
    }
    # Stock/MF alert rules: persist extra fields
    _pct_types = ("profit_threshold", "day_drop_threshold", "week_drop_threshold", "month_drop_threshold")
    _time_only_types = ("near_52w_high", "near_52w_low")
    rt = rule_data.get("rule_type", "")
    if rt in _pct_types:
        rule["threshold_pct"] = rule_data.get("threshold_pct", 25)
        rule["alert_time"] = rule_data.get("alert_time", "16:30")
    elif rt in _time_only_types:
        rule["alert_time"] = rule_data.get("alert_time", "16:30")
    rules.append(rule)
    _save_rules(email, user_id, rules)
    logger.info(f"[ExpiryRules] Created rule: {rule['category']}/{rule['rule_type']} for {user_id}")
    return rule


def delete_rule(email: str, user_id: str, rule_id: str) -> bool:
    rules = _load_rules(email, user_id)
    original_len = len(rules)
    rules = [r for r in rules if r["id"] != rule_id]
    if len(rules) < original_len:
        _save_rules(email, user_id, rules)
        logger.info(f"[ExpiryRules] Deleted rule: {rule_id}")
        return True
    return False


def get_rule_types() -> dict:
    return RULE_TYPES


# ── Evaluator ────────────────────────────────────────────

def evaluate_expiry_rules():
    from app import notification_service

    users = get_users()
    if not users:
        return

    for user in users:
        email = user.get("email", "")
        user_id = user.get("id", "")
        if not email or not user_id:
            continue

        rules = _load_rules(email, user_id)
        enabled_rules = [r for r in rules if r.get("enabled", True)]
        if not enabled_rules:
            continue

        instruments = _load_user_instruments(email, user_id)

        # Separate stock/MF alert rules from expiry rules
        _special_types = ("profit_threshold", "day_drop_threshold", "week_drop_threshold",
                          "month_drop_threshold", "near_52w_high", "near_52w_low")
        profit_rules = [r for r in enabled_rules if r.get("rule_type") in _special_types]
        expiry_rules_list = [r for r in enabled_rules if r.get("rule_type") not in _special_types]

        # Evaluate expiry rules (existing logic, unchanged)
        for rule in expiry_rules_list:
            category = rule.get("category", "")
            rule_type = rule.get("rule_type", "")
            days_threshold = rule.get("days", 30)

            for item in instruments.get(category, []):
                msg = _check_rule(item, category, rule_type, days_threshold)
                if msg:
                    from app import alert_service
                    cooldown_key = f"expiry_{rule['id']}"
                    if not alert_service._check_cooldown(cooldown_key, 1440):
                        continue
                    success = notification_service.notify(
                        "email", f"Portfolio Alert: {rule['category'].upper()}", msg,
                        user_email=email,
                    )
                    alert_service._record_history(
                        cooldown_key, f"Expiry: {rule['category']}/{rule['rule_type']}",
                        "email", msg, success,
                    )

        # Evaluate profit threshold rules
        for rule in profit_rules:
            _evaluate_profit_rule(rule, email, user_id, notification_service)


def _load_user_instruments(email: str, user_id: str) -> Dict[str, list]:  # pragma: no cover
    result = {"fd": [], "rd": [], "ppf": [], "nps": [], "si": [], "insurance": []}
    try:
        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return result

        try:
            from app.fd_database import get_all as get_fds
            result["fd"] = get_fds(dumps_dir)
        except Exception:
            pass
        try:
            from app.rd_database import get_all as get_rds
            result["rd"] = get_rds(dumps_dir)
        except Exception:
            pass
        try:
            from app.ppf_database import PPFDatabase
            result["ppf"] = PPFDatabase(dumps_dir).get_all()
        except Exception:
            pass
        try:
            from app.nps_database import NPSDatabase
            result["nps"] = NPSDatabase(dumps_dir).get_all()
        except Exception:
            pass
        try:
            from app.si_database import get_all as get_sis
            result["si"] = get_sis(dumps_dir)
        except Exception:
            pass
        try:
            from app.insurance_database import get_all as get_insurance
            result["insurance"] = get_insurance(dumps_dir)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"[ExpiryRules] Failed to load instruments for {user_id}: {e}")
    return result


def _check_rule(item: dict, category: str, rule_type: str, days_threshold: int) -> Optional[str]:
    status = item.get("status", "").lower()
    if status not in ("active",):
        return None

    name = item.get("name", "") or item.get("account_name", "") or item.get("bank", "") or item.get("beneficiary", "")

    if category in ("fd", "rd", "ppf"):
        days_left = item.get("days_to_maturity", -1)
        maturity_date = item.get("maturity_date", "")
        if rule_type == "on_maturity" and days_left == 0:
            return f"{category.upper()} '{name}' matures today ({maturity_date})!"
        if rule_type == "days_before_maturity" and 0 < days_left <= days_threshold:
            return f"{category.upper()} '{name}' matures in {days_left} day(s) on {maturity_date}."

    elif category in ("si", "insurance"):
        days_left = item.get("days_to_expiry", -1)
        expiry_date = item.get("expiry_date", "")
        label = "Insurance" if category == "insurance" else "Standing Instruction"
        if rule_type == "on_expiry" and days_left == 0:
            return f"{label} '{name}' expires today ({expiry_date})!"
        if rule_type == "days_before_expiry" and 0 < days_left <= days_threshold:
            return f"{label} '{name}' expires in {days_left} day(s) on {expiry_date}."

    elif category == "nps":
        if rule_type == "contribution_reminder":
            contributions = item.get("contributions", [])
            today = datetime.now()
            current_month = today.strftime("%Y-%m")
            has_this_month = any(c.get("date", "").startswith(current_month) for c in contributions)
            if not has_this_month and today.day >= 25:
                return f"NPS '{name}': No contribution recorded for {today.strftime('%B %Y')}."

    return None


# ── Profit Threshold Evaluation ─────────────────────────

def _is_within_alert_window(alert_time: str) -> bool:
    """Check if current time is within a 2-minute window of alert_time (HH:MM)."""
    try:
        now = datetime.now()
        parts = alert_time.split(":")
        target_h, target_m = int(parts[0]), int(parts[1])
        target = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        diff = abs((now - target).total_seconds())
        return diff <= 120  # 2-minute window
    except (ValueError, IndexError):
        return False


def _evaluate_profit_rule(rule: dict, email: str, user_id: str, notification_service):
    """Evaluate stock/MF alert rules: profit, drop (1D/1W/1M), 52W high/low."""
    from app import alert_service

    alert_time = rule.get("alert_time", "16:30")
    if not _is_within_alert_window(alert_time):
        return

    rule_type = rule.get("rule_type", "")
    cooldown_key = f"{rule_type}_{rule['id']}"
    if not alert_service._check_cooldown(cooldown_key, 1440):
        return

    category = rule.get("category", "")
    threshold = rule.get("threshold_pct", 25)

    qualifying_items = []
    subject = ""
    html_body = ""
    plain_body = ""
    history_label = ""
    history_msg = ""

    cat_label = "stocks" if category == "stocks" else "MF funds"

    if rule_type == "profit_threshold":
        if category == "stocks":
            qualifying_items = _get_stock_lots_above_threshold(email, user_id, threshold)
        elif category == "mf":
            qualifying_items = _get_mf_lots_above_threshold(email, user_id, threshold)
        if not qualifying_items:
            return
        subject = f"Portfolio Alert: {len(qualifying_items)} {'stock lots' if category == 'stocks' else 'MF units'} exceed {threshold}% profit"
        html_body = _build_profit_alert_html(qualifying_items, category, threshold)
        plain_body = _build_profit_alert_plain(qualifying_items, category, threshold)
        history_label = f"Profit: {category}/{threshold}%"
        history_msg = f"{len(qualifying_items)} lots exceed {threshold}%"

    elif rule_type in ("day_drop_threshold", "week_drop_threshold", "month_drop_threshold"):
        period_map = {"day_drop_threshold": "1D", "week_drop_threshold": "1W", "month_drop_threshold": "1M"}
        period = period_map[rule_type]
        if category == "stocks":
            qualifying_items = _get_stock_period_drops(email, user_id, threshold, period)
        elif category == "mf":
            qualifying_items = _get_mf_period_drops(email, user_id, threshold, period)
        if not qualifying_items:
            return
        subject = f"Portfolio Alert: {len(qualifying_items)} {cat_label} dropped >{threshold}% ({period})"
        html_body = _build_drop_alert_html(qualifying_items, category, threshold, period)
        plain_body = _build_drop_alert_plain(qualifying_items, category, threshold, period)
        history_label = f"Drop {period}: {category}/{threshold}%"
        history_msg = f"{len(qualifying_items)} items dropped >{threshold}% ({period})"

    elif rule_type in ("near_52w_high", "near_52w_low"):
        is_high = rule_type == "near_52w_high"
        if category == "stocks":
            qualifying_items = _get_stock_52w_hits(email, user_id, is_high)
        elif category == "mf":
            qualifying_items = _get_mf_52w_hits(email, user_id, is_high)
        if not qualifying_items:
            return
        label_hw = "52-week high" if is_high else "52-week low"
        subject = f"Portfolio Alert: {len(qualifying_items)} {cat_label} at {label_hw}"
        html_body = _build_52w_alert_html(qualifying_items, category, is_high)
        plain_body = _build_52w_alert_plain(qualifying_items, category, is_high)
        history_label = f"52W {'High' if is_high else 'Low'}: {category}"
        history_msg = f"{len(qualifying_items)} at {label_hw}"

    else:
        return

    success = notification_service.notify(
        "email", subject, plain_body, html_body=html_body,
        user_email=email,
    )
    alert_service._record_history(
        cooldown_key, history_label, "email", history_msg, success,
    )


def _get_stock_lots_above_threshold(email: str, user_id: str, threshold_pct: float) -> list:  # pragma: no cover
    """Get stock held lots where profit % >= threshold."""
    try:
        from app.xlsx_database import XlsxPortfolio
        from app import stock_service

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        db = XlsxPortfolio(dumps_dir / "Stocks", read_only=True)
        holdings, _, _ = db.get_all_data()
        if not holdings:
            return []

        # Get cached prices
        symbols = set((h.symbol, h.exchange) for h in holdings)
        live_data = stock_service.get_cached_prices(list(symbols))

        today = datetime.now()
        result = []
        for h in holdings:
            price_info = live_data.get(h.symbol)
            if not price_info:
                alt = "NSE" if h.exchange == "BSE" else "BSE"
                price_info = live_data.get(f"{h.symbol}:{alt}")
                if not price_info:
                    continue

            current_price = price_info.get("current_price", 0)
            if current_price <= 0 or h.buy_price <= 0:
                continue

            pct = (current_price - h.buy_price) / h.buy_price * 100
            if pct < threshold_pct:
                continue

            pl_inr = (current_price - h.buy_price) * h.quantity
            try:
                buy_dt = datetime.strptime(h.buy_date, "%Y-%m-%d")
                days_held = (today - buy_dt).days
                cost = h.buy_price * h.quantity
                pa = (pow(1 + pl_inr / cost, 365 / days_held) - 1) * 100 if days_held > 0 and cost > 0 else None
            except (ValueError, TypeError):
                pa = None

            result.append({
                "name": h.symbol,
                "exchange": h.exchange,
                "buy_date": h.buy_date,
                "qty": h.quantity,
                "buy_price": h.buy_price,
                "current_price": current_price,
                "pl_inr": round(pl_inr, 2),
                "pl_pct": round(pct, 2),
                "pl_pa": round(pa, 2) if pa is not None else None,
            })

        result.sort(key=lambda x: x["pl_pct"], reverse=True)
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] Stock profit eval error for {user_id}: {e}")
        return []


def _get_mf_lots_above_threshold(email: str, user_id: str, threshold_pct: float) -> list:  # pragma: no cover
    """Get MF held units where profit % >= threshold."""
    try:
        from app.mf_xlsx_database import MFXlsxPortfolio, fetch_live_navs

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        mf_dir = dumps_dir / "Mutual Funds"
        if not mf_dir.exists():
            return []

        db = MFXlsxPortfolio(mf_dir)
        all_codes = list(db._file_map.keys())
        if not all_codes:
            return []

        live_navs = fetch_live_navs(all_codes)

        today = datetime.now()
        result = []
        for fund_code in all_codes:
            try:
                holdings, _, idx_data = db._get_fund_data(fund_code)
            except Exception:
                continue

            name = db._name_map.get(fund_code, fund_code)
            current_nav = live_navs.get(fund_code, 0.0) or idx_data.get("current_nav", 0.0)
            if current_nav <= 0:
                continue

            for h in holdings:
                if h.buy_price <= 0:
                    continue
                pct = (current_nav - h.buy_price) / h.buy_price * 100
                if pct < threshold_pct:
                    continue

                pl_inr = (current_nav - h.buy_price) * h.units
                try:
                    buy_dt = datetime.strptime(h.buy_date, "%Y-%m-%d")
                    days_held = (today - buy_dt).days
                    cost = h.buy_price * h.units
                    pa = (pow(1 + pl_inr / cost, 365 / days_held) - 1) * 100 if days_held > 0 and cost > 0 else None
                except (ValueError, TypeError):
                    pa = None

                result.append({
                    "name": name,
                    "fund_code": fund_code,
                    "buy_date": h.buy_date,
                    "qty": round(h.units, 4),
                    "buy_price": round(h.buy_price, 4),
                    "current_price": round(current_nav, 4),
                    "pl_inr": round(pl_inr, 2),
                    "pl_pct": round(pct, 2),
                    "pl_pa": round(pa, 2) if pa is not None else None,
                })

        result.sort(key=lambda x: x["pl_pct"], reverse=True)
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] MF profit eval error for {user_id}: {e}")
        return []


def _fmt_inr(num: float) -> str:
    """Format number as INR with commas."""
    if num < 0:
        return f"-\u20b9{abs(num):,.2f}"
    return f"\u20b9{num:,.2f}"


def _build_profit_alert_html(lots: list, category: str, threshold: float) -> str:
    """Build HTML email body for profit threshold alert."""
    label = "Stock" if category == "stocks" else "Mutual Fund"
    name_col = "Stock" if category == "stocks" else "Fund"
    qty_col = "Qty" if category == "stocks" else "Units"

    rows = ""
    for lot in lots:
        pa_str = f"{lot['pl_pa']:+.1f}% p.a." if lot.get("pl_pa") is not None else "\u2014"
        rows += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #333;color:#fff">{lot['name']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;color:#aaa">{lot['buy_date']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{lot['qty']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(lot['buy_price'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(lot['current_price'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#00d26a">{_fmt_inr(lot['pl_inr'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#00d26a">+{lot['pl_pct']:.1f}%</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#00d26a">{pa_str}</td>
        </tr>"""

    total_pl = sum(l["pl_inr"] for l in lots)

    return f"""<div style="background:#1a1a2e;padding:24px;font-family:-apple-system,BlinkMacSystemFont,sans-serif">
        <h2 style="color:#fff;margin:0 0 4px">{len(lots)} {label} Lot{'s' if len(lots)!=1 else ''} Exceed {threshold:.0f}% Profit</h2>
        <p style="color:#888;margin:0 0 16px;font-size:13px">Total unrealized profit: <span style="color:#00d26a;font-weight:600">{_fmt_inr(total_pl)}</span></p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
                <tr style="border-bottom:2px solid #444">
                    <th style="padding:8px 12px;text-align:left;color:#888;text-transform:uppercase;font-size:11px">{name_col}</th>
                    <th style="padding:8px 12px;text-align:left;color:#888;text-transform:uppercase;font-size:11px">Buy Date</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">{qty_col}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Buy Price</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Current</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">P/L</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">%</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">% p.a.</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="color:#555;font-size:11px;margin:16px 0 0">Portfolio Dashboard \u2014 Profit Alert</p>
    </div>"""


def _build_profit_alert_plain(lots: list, category: str, threshold: float) -> str:
    """Build plain text email body for profit threshold alert."""
    label = "Stock" if category == "stocks" else "MF"
    lines = [f"{len(lots)} {label} lots exceed {threshold:.0f}% profit:\n"]
    for lot in lots:
        pa_str = f", {lot['pl_pa']:+.1f}% p.a." if lot.get("pl_pa") is not None else ""
        lines.append(
            f"  {lot['name']} | Buy: {lot['buy_date']} | {lot['qty']} @ {_fmt_inr(lot['buy_price'])} "
            f"\u2192 {_fmt_inr(lot['current_price'])} | P/L: {_fmt_inr(lot['pl_inr'])} (+{lot['pl_pct']:.1f}%{pa_str})"
        )
    total_pl = sum(l["pl_inr"] for l in lots)
    lines.append(f"\nTotal unrealized profit: {_fmt_inr(total_pl)}")
    return "\n".join(lines)


# ── Day Drop Evaluation ─────────────────────────────────

def _get_stock_period_drops(email: str, user_id: str, threshold_pct: float, period: str = "1D") -> list:  # pragma: no cover
    """Get stocks where period price change is negative and exceeds threshold.
    period: '1D', '1W', or '1M'."""
    try:
        from app.xlsx_database import XlsxPortfolio
        from app import stock_service

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        db = XlsxPortfolio(dumps_dir / "Stocks", read_only=True)
        holdings, _, _ = db.get_all_data()
        if not holdings:
            return []

        symbol_data = {}
        for h in holdings:
            if h.symbol not in symbol_data:
                symbol_data[h.symbol] = {"exchange": h.exchange, "qty": 0, "invested": 0}
            symbol_data[h.symbol]["qty"] += h.quantity
            symbol_data[h.symbol]["invested"] += h.buy_price * h.quantity

        symbols = [(sym, d["exchange"]) for sym, d in symbol_data.items()]
        live_data = stock_service.get_cached_prices(symbols)

        pct_key = {"1D": "day_change_pct", "1W": "week_change_pct", "1M": "month_change_pct"}[period]

        result = []
        for sym, info in symbol_data.items():
            price_info = live_data.get(sym)
            if not price_info:
                alt = "NSE" if info["exchange"] == "BSE" else "BSE"
                price_info = live_data.get(f"{sym}:{alt}")
                if not price_info:
                    continue

            change_pct = price_info.get(pct_key, 0)
            if change_pct >= 0 or abs(change_pct) < threshold_pct:
                continue

            current_price = price_info.get("current_price", 0)
            total_value = current_price * info["qty"]

            result.append({
                "name": sym,
                "exchange": info["exchange"],
                "qty": info["qty"],
                "current_price": round(current_price, 2),
                "day_change_pct": round(change_pct, 2),
                "day_loss_inr": round(change_pct / 100 * total_value, 2),
                "total_value": round(total_value, 2),
                "prev_close": round(current_price / (1 + change_pct / 100), 2) if change_pct != -100 else 0,
                "day_change": round(change_pct / 100 * current_price, 2),
            })

        result.sort(key=lambda x: x["day_change_pct"])
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] Stock {period}-drop eval error for {user_id}: {e}")
        return []


def _get_mf_period_drops(email: str, user_id: str, threshold_pct: float, period: str = "1D") -> list:  # pragma: no cover
    """Get MF funds where period NAV change is negative and exceeds threshold."""
    try:
        from app.mf_xlsx_database import MFXlsxPortfolio, fetch_live_navs, compute_nav_changes

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        mf_dir = dumps_dir / "Mutual Funds"
        if not mf_dir.exists():
            return []

        db = MFXlsxPortfolio(mf_dir)
        all_codes = list(db._file_map.keys())
        if not all_codes:
            return []

        live_navs = fetch_live_navs(all_codes)
        pct_key = {"1D": "day_change_pct", "1W": "week_change_pct", "1M": "month_change_pct"}[period]

        result = []
        for fund_code in all_codes:
            try:
                holdings, _, idx_data = db._get_fund_data(fund_code)
            except Exception:
                continue

            name = db._name_map.get(fund_code, fund_code)
            current_nav = live_navs.get(fund_code, 0.0) or idx_data.get("current_nav", 0.0)
            if current_nav <= 0:
                continue

            total_units = sum(h.units for h in holdings)
            if total_units <= 0:
                continue

            nav_changes = compute_nav_changes(fund_code, name, current_nav)
            change_pct = nav_changes.get(pct_key, 0)

            if change_pct >= 0 or abs(change_pct) < threshold_pct:
                continue

            total_value = current_nav * total_units

            result.append({
                "name": name,
                "fund_code": fund_code,
                "qty": round(total_units, 4),
                "current_price": round(current_nav, 4),
                "day_change_pct": round(change_pct, 2),
                "day_loss_inr": round(change_pct / 100 * total_value, 2),
                "total_value": round(total_value, 2),
                "prev_close": round(current_nav / (1 + change_pct / 100), 4) if change_pct != -100 else 0,
                "day_change": round(change_pct / 100 * current_nav, 4),
            })

        result.sort(key=lambda x: x["day_change_pct"])
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] MF {period}-drop eval error for {user_id}: {e}")
        return []


def _get_stock_52w_hits(email: str, user_id: str, is_high: bool) -> list:  # pragma: no cover
    """Get stocks at or near 52-week high (is_high=True) or low (is_high=False)."""
    try:
        from app.xlsx_database import XlsxPortfolio
        from app import stock_service

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        db = XlsxPortfolio(dumps_dir / "Stocks", read_only=True)
        holdings, _, _ = db.get_all_data()
        if not holdings:
            return []

        symbol_data = {}
        for h in holdings:
            if h.symbol not in symbol_data:
                symbol_data[h.symbol] = {"exchange": h.exchange, "qty": 0}
            symbol_data[h.symbol]["qty"] += h.quantity

        symbols = [(sym, d["exchange"]) for sym, d in symbol_data.items()]
        live_data = stock_service.get_cached_prices(symbols)

        result = []
        for sym, info in symbol_data.items():
            price_info = live_data.get(sym)
            if not price_info:
                alt = "NSE" if info["exchange"] == "BSE" else "BSE"
                price_info = live_data.get(f"{sym}:{alt}")
                if not price_info:
                    continue

            current_price = price_info.get("current_price", 0)
            w52_high = price_info.get("week_52_high", 0)
            w52_low = price_info.get("week_52_low", 0)
            if current_price <= 0:
                continue

            if is_high:
                if w52_high <= 0 or current_price < w52_high * 0.98:
                    continue  # Within 2% of 52W high
                pct_from = round((current_price / w52_high - 1) * 100, 2) if w52_high > 0 else 0
                ref_price = w52_high
            else:
                if w52_low <= 0 or current_price > w52_low * 1.02:
                    continue  # Within 2% of 52W low
                pct_from = round((current_price / w52_low - 1) * 100, 2) if w52_low > 0 else 0
                ref_price = w52_low

            total_value = current_price * info["qty"]

            result.append({
                "name": sym,
                "exchange": info["exchange"],
                "qty": info["qty"],
                "current_price": round(current_price, 2),
                "ref_price": round(ref_price, 2),
                "pct_from_ref": pct_from,
                "total_value": round(total_value, 2),
                "w52_high": round(w52_high, 2),
                "w52_low": round(w52_low, 2),
            })

        result.sort(key=lambda x: abs(x["pct_from_ref"]))
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] Stock 52W eval error for {user_id}: {e}")
        return []


def _get_mf_52w_hits(email: str, user_id: str, is_high: bool) -> list:  # pragma: no cover
    """Get MF funds at or near 52-week high/low NAV."""
    try:
        from app.mf_xlsx_database import MFXlsxPortfolio, fetch_live_navs, compute_nav_changes

        dumps_dir = get_user_dumps_dir(user_id, email)
        if not dumps_dir:
            return []

        mf_dir = dumps_dir / "Mutual Funds"
        if not mf_dir.exists():
            return []

        db = MFXlsxPortfolio(mf_dir)
        all_codes = list(db._file_map.keys())
        if not all_codes:
            return []

        live_navs = fetch_live_navs(all_codes)

        result = []
        for fund_code in all_codes:
            try:
                holdings, _, idx_data = db._get_fund_data(fund_code)
            except Exception:
                continue

            name = db._name_map.get(fund_code, fund_code)
            current_nav = live_navs.get(fund_code, 0.0) or idx_data.get("current_nav", 0.0)
            if current_nav <= 0:
                continue

            total_units = sum(h.units for h in holdings)
            if total_units <= 0:
                continue

            nav_changes = compute_nav_changes(fund_code, name, current_nav)
            w52_high = nav_changes.get("week_52_high", 0) or idx_data.get("week_52_high", 0)
            w52_low = nav_changes.get("week_52_low", 0) or idx_data.get("week_52_low", 0)

            if is_high:
                if w52_high <= 0 or current_nav < w52_high * 0.98:
                    continue
                pct_from = round((current_nav / w52_high - 1) * 100, 2)
                ref_price = w52_high
            else:
                if w52_low <= 0 or current_nav > w52_low * 1.02:
                    continue
                pct_from = round((current_nav / w52_low - 1) * 100, 2)
                ref_price = w52_low

            total_value = current_nav * total_units

            result.append({
                "name": name,
                "fund_code": fund_code,
                "qty": round(total_units, 4),
                "current_price": round(current_nav, 4),
                "ref_price": round(ref_price, 4),
                "pct_from_ref": pct_from,
                "total_value": round(total_value, 2),
                "w52_high": round(w52_high, 4),
                "w52_low": round(w52_low, 4),
            })

        result.sort(key=lambda x: abs(x["pct_from_ref"]))
        return result
    except Exception as e:
        logger.error(f"[ExpiryRules] MF 52W eval error for {user_id}: {e}")
        return []


def _build_drop_alert_html(items: list, category: str, threshold: float, period: str = "1D") -> str:
    """Build HTML email body for period drop alert."""
    label = "Stock" if category == "stocks" else "Mutual Fund"
    name_col = "Stock" if category == "stocks" else "Fund"
    qty_col = "Qty" if category == "stocks" else "Units"
    period_label = {"1D": "Today", "1W": "This Week", "1M": "This Month"}.get(period, period)

    rows = ""
    for item in items:
        rows += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #333;color:#fff">{item['name']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{item['qty']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(item['prev_close'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#ff4d4d">{_fmt_inr(item['current_price'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#ff4d4d">{item['day_change_pct']:.2f}%</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#ff4d4d">{_fmt_inr(item['day_loss_inr'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(item['total_value'])}</td>
        </tr>"""

    total_loss = sum(i["day_loss_inr"] for i in items)

    return f"""<div style="background:#1a1a2e;padding:24px;font-family:-apple-system,BlinkMacSystemFont,sans-serif">
        <h2 style="color:#ff4d4d;margin:0 0 4px">{len(items)} {label}{'s' if len(items)!=1 else ''} Dropped &gt;{threshold:.0f}% ({period_label})</h2>
        <p style="color:#888;margin:0 0 16px;font-size:13px">Total loss: <span style="color:#ff4d4d;font-weight:600">{_fmt_inr(total_loss)}</span></p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
                <tr style="border-bottom:2px solid #444">
                    <th style="padding:8px 12px;text-align:left;color:#888;text-transform:uppercase;font-size:11px">{name_col}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">{qty_col}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Prev</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Current</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">{period} %</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Loss</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Value</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="color:#555;font-size:11px;margin:16px 0 0">Portfolio Dashboard \u2014 {period} Drop Alert</p>
    </div>"""


def _build_drop_alert_plain(items: list, category: str, threshold: float, period: str = "1D") -> str:
    """Build plain text email body for period drop alert."""
    label = "Stock" if category == "stocks" else "MF"
    lines = [f"{len(items)} {label} dropped >{threshold:.0f}% ({period}):\n"]
    for item in items:
        lines.append(
            f"  {item['name']} | {item['qty']} units | "
            f"{_fmt_inr(item['prev_close'])} \u2192 {_fmt_inr(item['current_price'])} "
            f"({item['day_change_pct']:.2f}%) | Loss: {_fmt_inr(item['day_loss_inr'])} | Value: {_fmt_inr(item['total_value'])}"
        )
    total_loss = sum(i["day_loss_inr"] for i in items)
    lines.append(f"\nTotal loss: {_fmt_inr(total_loss)}")
    return "\n".join(lines)


def _build_52w_alert_html(items: list, category: str, is_high: bool) -> str:
    """Build HTML email body for 52-week high/low alert."""
    label = "Stock" if category == "stocks" else "Mutual Fund"
    name_col = "Stock" if category == "stocks" else "Fund"
    qty_col = "Qty" if category == "stocks" else "Units"
    hw_label = "52-Week High" if is_high else "52-Week Low"
    color = "#00d26a" if is_high else "#ff4d4d"

    rows = ""
    for item in items:
        rows += f"""<tr>
            <td style="padding:8px 12px;border-bottom:1px solid #333;color:#fff">{item['name']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{item['qty']}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:{color}">{_fmt_inr(item['current_price'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(item['w52_high'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(item['w52_low'])}</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:{color}">{item['pct_from_ref']:+.1f}%</td>
            <td style="padding:8px 12px;border-bottom:1px solid #333;text-align:right;color:#fff">{_fmt_inr(item['total_value'])}</td>
        </tr>"""

    return f"""<div style="background:#1a1a2e;padding:24px;font-family:-apple-system,BlinkMacSystemFont,sans-serif">
        <h2 style="color:{color};margin:0 0 4px">{len(items)} {label}{'s' if len(items)!=1 else ''} at {hw_label}</h2>
        <p style="color:#888;margin:0 0 16px;font-size:13px">Within 2% of {hw_label.lower()}</p>
        <table style="width:100%;border-collapse:collapse;font-size:13px">
            <thead>
                <tr style="border-bottom:2px solid #444">
                    <th style="padding:8px 12px;text-align:left;color:#888;text-transform:uppercase;font-size:11px">{name_col}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">{qty_col}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Current</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">52W High</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">52W Low</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">% from {hw_label.split()[1]}</th>
                    <th style="padding:8px 12px;text-align:right;color:#888;text-transform:uppercase;font-size:11px">Value</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        <p style="color:#555;font-size:11px;margin:16px 0 0">Portfolio Dashboard \u2014 {hw_label} Alert</p>
    </div>"""


def _build_52w_alert_plain(items: list, category: str, is_high: bool) -> str:
    """Build plain text email body for 52-week high/low alert."""
    label = "Stock" if category == "stocks" else "MF"
    hw_label = "52-week high" if is_high else "52-week low"
    lines = [f"{len(items)} {label} at or near {hw_label}:\n"]
    for item in items:
        lines.append(
            f"  {item['name']} | {item['qty']} units | Current: {_fmt_inr(item['current_price'])} "
            f"| 52W H: {_fmt_inr(item['w52_high'])} L: {_fmt_inr(item['w52_low'])} "
            f"| {item['pct_from_ref']:+.1f}% from {hw_label} | Value: {_fmt_inr(item['total_value'])}"
        )
    return "\n".join(lines)
