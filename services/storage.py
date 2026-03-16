from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CALL_HISTORY_PATH = DATA_DIR / "call_history.json"


def _ensure_store() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not CALL_HISTORY_PATH.exists():
        CALL_HISTORY_PATH.write_text("[]", encoding="utf-8")


def load_call_history() -> list[dict]:
    _ensure_store()
    return json.loads(CALL_HISTORY_PATH.read_text(encoding="utf-8"))


def save_call_record(record: dict) -> None:
    _ensure_store()
    history = load_call_history()
    history.insert(0, {**record, "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z"})
    CALL_HISTORY_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")
