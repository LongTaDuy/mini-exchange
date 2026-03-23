from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    """A limit order. `quantity` is the remaining size (updated as fills occur)."""

    order_id: str
    side: Side
    price: Decimal
    quantity: Decimal
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        from mini_exchange.validation import validate_limit_order

        validate_limit_order(self)
