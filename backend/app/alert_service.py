"""
Alert rules engine with background evaluation and notification history.

Loads/saves alert rules from backend/data/alerts.json.
Runs a background thread that periodically evaluates rules.
Tracks notification history to enforce cooldown periods.
Condition evaluators are registered via register_evaluator() — plugged in later.
"""
import os
import json
import uuid
import time
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Callable, Tuple, Optional

from . import notification_service

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ALERTS_FILE = _DATA_DIR / "alerts.json"
_HISTORY_FILE = _DATA_DIR / "alert_history.json"

_lock = threading.Lock()
_bg_running = False
_bg_thread = None
_EVAL_INTERVAL = 60  # seconds between evaluation cycles

# Registry: condition_type → evaluator function
# Each evaluator takes (condition_dict) → (triggered: bool, message: str)
_condition_evaluators: Dict[str, Callable[[dict], Tuple[bool, str]]] = {}


def register_evaluator(condition_type: str, fn: Callable[[dict], Tuple[bool, str]]):
    """Register a condition evaluator function.
    fn(condition_dict) should return (triggered: bool, message: str)."""
    _condition_evaluators[condition_type] = fn
    logger.info(f"[Alerts] Registered evaluator for condition type: {condition_type}")


# ── Persistence ──────────────────────────────────────────

def _load_alerts() -> list:
    try:
        with open(_ALERTS_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_alerts(alerts: list):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_ALERTS_FILE, "w") as f:
        json.dump(alerts, f, indent=2)


def _load_history() -> list:
    try:
        with open(_HISTORY_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_history(history: list):
    # Keep last 200 entries
    if len(history) > 200:
        history = history[-200:]
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


# ── Public API ───────────────────────────────────────────

def get_alerts() -> list:
    with _lock:
        return _load_alerts()


def create_or_update_alert(data: dict) -> dict:
    with _lock:
        alerts = _load_alerts()
        now = datetime.now().isoformat(timespec="seconds")

        alert_id = data.get("id", "").strip()
        if alert_id:
            # Update existing
            for i, a in enumerate(alerts):
                if a["id"] == alert_id:
                    alerts[i] = {**a, **data, "updated_at": now}
                    _save_alerts(alerts)
                    logger.info(f"[Alerts] Updated alert: {alerts[i].get('name', alert_id)}")
                    return alerts[i]

        # Create new
        alert = {
            "id": str(uuid.uuid4())[:8],
            "name": data.get("name", "Unnamed Alert"),
            "enabled": data.get("enabled", True),
            "channel": data.get("channel", "telegram"),
            "condition": data.get("condition", {}),
            "cooldown_minutes": data.get("cooldown_minutes", 60),
            "created_at": now,
            "updated_at": now,
        }
        alerts.append(alert)
        _save_alerts(alerts)
        logger.info(f"[Alerts] Created alert: {alert['name']} ({alert['id']})")
        return alert


def delete_alert(alert_id: str) -> bool:
    with _lock:
        alerts = _load_alerts()
        original_len = len(alerts)
        alerts = [a for a in alerts if a["id"] != alert_id]
        if len(alerts) < original_len:
            _save_alerts(alerts)
            logger.info(f"[Alerts] Deleted alert: {alert_id}")
            return True
        return False


def get_history(limit: int = 50) -> list:
    with _lock:
        history = _load_history()
    return list(reversed(history))[:limit]


# ── Cooldown & History ───────────────────────────────────

def _check_cooldown(alert_id: str, cooldown_minutes: int) -> bool:
    """Returns True if cooldown has elapsed (safe to notify)."""
    history = _load_history()
    cutoff = (datetime.now() - timedelta(minutes=cooldown_minutes)).isoformat()
    for entry in reversed(history):
        if entry.get("alert_id") == alert_id and entry.get("success"):
            if entry.get("timestamp", "") > cutoff:
                return False  # Still in cooldown
    return True


def _record_history(alert_id: str, alert_name: str, channel: str, message: str, success: bool):
    history = _load_history()
    history.append({
        "id": str(uuid.uuid4())[:8],
        "alert_id": alert_id,
        "alert_name": alert_name,
        "channel": channel,
        "message": message[:500],
        "success": success,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })
    _save_history(history)


# ── Background Evaluation ────────────────────────────────

def _evaluate_once():
    """Evaluate all registered evaluators, then any custom alerts from alerts.json."""
    # 1. Run all registered evaluators directly (e.g. expiry_check)
    #    These handle their own notification logic internally.
    for ctype, fn in _condition_evaluators.items():
        try:
            fn({})
        except Exception as e:
            logger.error(f"[Alerts] Evaluator error for {ctype}: {e}")

    # 2. Evaluate custom alerts from alerts.json (if any)
    with _lock:
        alerts = _load_alerts()

    for alert in alerts:
        if not alert.get("enabled", True):
            continue

        condition = alert.get("condition", {})
        ctype = condition.get("type", "")
        if not ctype or ctype not in _condition_evaluators:
            continue

        try:
            triggered, message = _condition_evaluators[ctype](condition)
        except Exception as e:
            logger.error(f"[Alerts] Evaluator error for {alert.get('name', '?')}: {e}")
            continue

        if not triggered:
            continue

        # Check cooldown
        with _lock:
            if not _check_cooldown(alert["id"], alert.get("cooldown_minutes", 60)):
                continue

        # Send notification
        channel = alert.get("channel", "telegram")
        success = notification_service.notify(channel, alert.get("name", "Alert"), message)

        with _lock:
            _record_history(alert["id"], alert.get("name", ""), channel, message, success)


def _bg_loop():
    """Background loop: evaluate alert rules every EVAL_INTERVAL seconds."""
    logger.info(f"[Alerts] Background evaluation started (every {_EVAL_INTERVAL}s)")
    while _bg_running:
        try:
            _evaluate_once()
        except Exception as e:
            logger.error(f"[Alerts] Evaluation error: {e}")
        # Sleep in 1s chunks so we can exit promptly
        for _ in range(_EVAL_INTERVAL):
            if not _bg_running:
                break
            time.sleep(1)


def start_alert_bg_thread():
    global _bg_thread, _bg_running
    if _bg_running:
        return
    _bg_running = True
    _bg_thread = threading.Thread(target=_bg_loop, daemon=True)
    _bg_thread.start()


def stop_alert_bg_thread():
    global _bg_running
    _bg_running = False


# ── Test Notification ────────────────────────────────────

def send_test_notification(channel: str = "all", message: str = None) -> dict:
    """Send a test notification to verify channel configuration."""
    msg = message or "Test notification from Portfolio Dashboard"
    success = notification_service.notify(channel, "Test Alert", msg)
    status = notification_service.get_channel_status()
    return {
        "success": success,
        "channel": channel,
        "message": msg,
        "channels": status,
    }
