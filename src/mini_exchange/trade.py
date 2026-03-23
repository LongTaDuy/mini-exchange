from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Trade:
    """One execution between a resting (maker) order and the aggressor."""

    trade_id: str
    price: Decimal
    quantity: Decimal
    buy_order_id: str
    sell_order_id: str
