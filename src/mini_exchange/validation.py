from __future__ import annotations

from decimal import Decimal
from typing import NoReturn

from mini_exchange.errors import InvalidOrderError
from mini_exchange.event_log import log_event
from mini_exchange.order import Order, Side


def _reject(reason: str) -> NoReturn:
    log_event("validation_failure", source="order", reason=reason)
    raise InvalidOrderError(reason)


def validate_limit_order(order: Order) -> None:
    """
    Ensure a limit order is safe to process. Call before mutating the book or order qty.

    Raises InvalidOrderError on failure (finite, positive price and quantity; valid ids).
    """
    if not isinstance(order.order_id, str) or not order.order_id.strip():
        _reject("order_id must be a non-empty string")
    if not isinstance(order.side, Side):
        _reject("side must be Side.BUY or Side.SELL")
    if not isinstance(order.price, Decimal):
        _reject("price must be a Decimal")
    if not isinstance(order.quantity, Decimal):
        _reject("quantity must be a Decimal")
    if not order.price.is_finite():
        _reject("price must be finite (not NaN or infinity)")
    if order.price <= 0:
        _reject("price must be positive")
    if not order.quantity.is_finite():
        _reject("quantity must be finite (not NaN or infinity)")
    if order.quantity <= 0:
        _reject("quantity must be positive")
