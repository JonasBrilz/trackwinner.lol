"""Shared JSON-file cache helpers for prep modules."""
import json
import pathlib
from datetime import date


def load(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save(path: pathlib.Path, data: dict):
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass


def is_fresh(cached_date: str, max_days: int) -> bool:
    try:
        return (date.today() - date.fromisoformat(cached_date)).days < max_days
    except Exception:
        return False
