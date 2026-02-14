"""
SIP (Systematic Investment Plan) configuration manager.
Stores SIP configs in a JSON file and provides methods to manage them.
"""

import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

_SIP_CONFIG_FILE = Path(__file__).parent.parent.parent / "dumps" / "sip_config.json"


class SIPManager:
    def __init__(self, config_file: str | Path = _SIP_CONFIG_FILE):
        self.config_file = Path(config_file)
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self):
        """Create config file if it doesn't exist."""
        if not self.config_file.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            self.config_file.write_text(json.dumps({"sip_configs": []}, indent=2))

    # ── Read / Write ─────────────────────────────────────

    def load_configs(self) -> List[dict]:
        """Load all SIP configurations."""
        with self._lock:
            try:
                data = json.loads(self.config_file.read_text())
                return data.get("sip_configs", [])
            except (json.JSONDecodeError, FileNotFoundError):
                return []

    def _save_configs(self, configs: List[dict]):
        """Save SIP configurations to file."""
        with self._lock:
            self.config_file.write_text(
                json.dumps({"sip_configs": configs}, indent=2, default=str)
            )

    # ── CRUD ─────────────────────────────────────────────

    def add_sip(
        self,
        fund_code: str,
        fund_name: str,
        amount: float,
        frequency: str = "monthly",
        sip_date: int = 1,
        start_date: str = "",
        end_date: Optional[str] = None,
        enabled: bool = True,
        notes: str = "",
    ) -> dict:
        """Add or update a SIP configuration for a fund."""
        configs = self.load_configs()

        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")

        next_sip = self._compute_next_sip_date(
            frequency, sip_date, start_date
        )

        new_config = {
            "fund_code": fund_code,
            "fund_name": fund_name,
            "amount": amount,
            "frequency": frequency,
            "sip_date": sip_date,
            "start_date": start_date,
            "end_date": end_date,
            "enabled": enabled,
            "next_sip_date": next_sip,
            "last_processed": None,
            "notes": notes,
        }

        # Update if exists, else add
        found = False
        for i, c in enumerate(configs):
            if c["fund_code"] == fund_code:
                configs[i] = new_config
                found = True
                break
        if not found:
            configs.append(new_config)

        self._save_configs(configs)
        return new_config

    def update_sip(self, fund_code: str, **kwargs) -> dict:
        """Update specific fields of an existing SIP."""
        configs = self.load_configs()
        for i, c in enumerate(configs):
            if c["fund_code"] == fund_code:
                for k, v in kwargs.items():
                    if k in c:
                        c[k] = v
                # Recompute next_sip_date if frequency/sip_date changed
                if "frequency" in kwargs or "sip_date" in kwargs:
                    c["next_sip_date"] = self._compute_next_sip_date(
                        c["frequency"], c["sip_date"],
                        c.get("last_processed") or c["start_date"]
                    )
                configs[i] = c
                self._save_configs(configs)
                return c
        raise ValueError(f"SIP config for {fund_code} not found")

    def delete_sip(self, fund_code: str):
        """Delete a SIP configuration."""
        configs = self.load_configs()
        configs = [c for c in configs if c["fund_code"] != fund_code]
        self._save_configs(configs)

    # ── SIP Processing ───────────────────────────────────

    def get_pending_sips(self) -> List[dict]:
        """Get SIPs that are due for processing (next_sip_date <= today)."""
        today = datetime.now().strftime("%Y-%m-%d")
        configs = self.load_configs()
        pending = []
        for c in configs:
            if not c.get("enabled", True):
                continue
            if c.get("end_date") and c["end_date"] < today:
                continue
            if c.get("next_sip_date", "") <= today:
                pending.append(c)
        return pending

    def mark_processed(self, fund_code: str, processed_date: str = ""):
        """Mark a SIP as processed and advance the next_sip_date."""
        if not processed_date:
            processed_date = datetime.now().strftime("%Y-%m-%d")

        configs = self.load_configs()
        for i, c in enumerate(configs):
            if c["fund_code"] == fund_code:
                c["last_processed"] = processed_date
                c["next_sip_date"] = self._compute_next_sip_date(
                    c["frequency"], c["sip_date"], processed_date
                )
                configs[i] = c
                self._save_configs(configs)
                return c
        raise ValueError(f"SIP config for {fund_code} not found")

    # ── Helper ───────────────────────────────────────────

    @staticmethod
    def _compute_next_sip_date(
        frequency: str, sip_date: int, from_date: str
    ) -> str:
        """Compute the next SIP execution date after `from_date`."""
        try:
            base = datetime.strptime(from_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            base = datetime.now()

        today = datetime.now()
        # Start from whichever is later: base or today
        ref = max(base, today)

        if frequency == "weekly":
            # sip_date = 1 (Mon) to 7 (Sun), map to Python weekday (0=Mon to 6=Sun)
            target_weekday = max(0, min(6, sip_date - 1))
            days_ahead = target_weekday - ref.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (ref + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        elif frequency == "quarterly":
            # Jump forward 3 months from base, land on sip_date
            month = ref.month
            year = ref.year
            # Next quarter boundary
            next_month = month + 3
            if next_month > 12:
                next_month -= 12
                year += 1
            day = min(sip_date, 28)
            candidate = datetime(year, next_month, day)
            if candidate <= ref:
                next_month += 3
                if next_month > 12:
                    next_month -= 12
                    year += 1
                candidate = datetime(year, next_month, day)
            return candidate.strftime("%Y-%m-%d")

        else:  # monthly (default)
            day = min(sip_date, 28)
            # Try this month first
            candidate = datetime(ref.year, ref.month, day)
            if candidate <= ref:
                # Move to next month
                month = ref.month + 1
                year = ref.year
                if month > 12:
                    month = 1
                    year += 1
                candidate = datetime(year, month, day)
            return candidate.strftime("%Y-%m-%d")


# Module-level singleton
sip_mgr = SIPManager()
