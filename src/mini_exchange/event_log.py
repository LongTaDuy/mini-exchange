"""
Structured, concise logs for operations and failures.

Each line is a single JSON object: ``{"event": "...", ...}``. Use::

    logging.getLogger("mini_exchange").setLevel(logging.INFO)

to see events (default root level WARNING hides INFO).
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger("mini_exchange")


def _json_default(obj: Any) -> str:
    if isinstance(obj, Decimal):
        return str(obj)
    return str(obj)


def log_event(event: str, **fields: Any) -> None:
    """Emit one structured log line (INFO)."""
    payload: dict[str, Any] = {"event": event}
    for k, v in fields.items():
        if v is not None:
            payload[k] = v
    line = json.dumps(payload, default=_json_default, separators=(",", ":"))
    logger.info("%s", line)
