"""Event log: one JSON object per line in logs/coach.log.

The console is not visible after the fact, so everything needed to work out what happened
in a game goes here: client phases, plans with their timing and cost, key presses that
triggered a screen read, item set writes, and errors.
"""
from __future__ import annotations

import json
import threading
import time

from . import config

_lock = threading.Lock()
_MAX_BYTES = 5_000_000


def log(event: str, **fields):
    """Append one event. Never raises: logging must not break the coach."""
    line = json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event, **fields},
                      ensure_ascii=False, default=str)
    try:
        with _lock:
            path = config.LOG_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and path.stat().st_size > _MAX_BYTES:
                path.replace(path.with_suffix(".old.log"))      # keep one previous file
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except OSError:
        pass
