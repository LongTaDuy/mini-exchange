"""
Shared test helpers.

Ensures `tests/` is on `sys.path` when runners start from the repo root
(e.g. `python -m unittest tests.test_foo`) so `import fixtures` resolves.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

from mini_exchange.order import Order, Side

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))


def limit_order(
    order_id: str,
    side: Side,
    price: str,
    qty: str,
    *,
    ts: float = 0.0,
) -> Order:
    """Build a validated limit `Order` from string decimals (readable in tests)."""
    return Order(order_id, side, Decimal(price), Decimal(qty), timestamp=ts)
