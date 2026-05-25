"""User settings persisted as JSON in the app's data directory."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


_CONFIG_DIR = Path(os.environ.get("PRICERATOR_DATA", Path.home() / ".pricerator"))
_CONFIG_FILE = _CONFIG_DIR / "settings.json"

REFRESH_HOURS: dict[str, int | None] = {
    "manual": None,
    "6h": 6,
    "12h": 12,
    "24h": 24,
}


@dataclass
class Settings:
    theme: str = "light"                  # "light" | "dark" | "kawaii"
    threshold_nonfoil_cents: int = 100
    threshold_foil_cents: int = 100
    threshold_etched_cents: int = 100
    refresh_interval: str = "24h"         # key in REFRESH_HOURS
    notifications_enabled: bool = True
    last_refreshed_at: float | None = None  # epoch seconds

    def refresh_hours(self) -> int | None:
        return REFRESH_HOURS.get(self.refresh_interval)

    def threshold_for(self, foil_type: str) -> int:
        if foil_type == "foil":
            return self.threshold_foil_cents
        if foil_type == "etched":
            return self.threshold_etched_cents
        return self.threshold_nonfoil_cents


def data_dir() -> Path:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return _CONFIG_DIR


def load() -> Settings:
    try:
        raw = json.loads(_CONFIG_FILE.read_text())
        return Settings(**{k: v for k, v in raw.items() if k in Settings.__dataclass_fields__})
    except (FileNotFoundError, json.JSONDecodeError, TypeError):
        return Settings()


def save(s: Settings) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(asdict(s), indent=2))
