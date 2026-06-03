"""Serialize core domain objects into stable, JSON-friendly dicts.

Every `Decimal` is rendered as a string so JSON consumers never see floats.
These helpers return plain dicts that match the response models in
`schemas.py`; FastAPI validates them against those models.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mini_exchange import Order, OrderBook, Trade


def serialize_trade(trade: Trade) -> Dict[str, Any]:
    return {
        "trade_id": trade.trade_id,
        "price": str(trade.price),
        "quantity": str(trade.quantity),
        "buy_order_id": trade.buy_order_id,
        "sell_order_id": trade.sell_order_id,
    }


def serialize_order(order: Order) -> Dict[str, Any]:
    """Resting-order detail view (id, side, price, remaining quantity, ts)."""
    return {
        "order_id": order.order_id,
        "side": order.side.value,
        "price": str(order.price),
        "quantity": str(order.quantity),
        "timestamp": order.timestamp,
    }


def top_of_book(book: OrderBook) -> Dict[str, Optional[str]]:
    best_bid = book.best_bid_price()
    best_ask = book.best_ask_price()
    return {
        "best_bid": None if best_bid is None else str(best_bid),
        "best_ask": None if best_ask is None else str(best_ask),
    }


def _levels(side: Any) -> List[Dict[str, Any]]:
    levels: List[Dict[str, Any]] = []
    for price, orders in side.items():
        levels.append(
            {
                "price": str(price),
                "orders": [
                    {"order_id": o.order_id, "quantity": str(o.quantity)}
                    for o in orders
                ],
            }
        )
    return levels


def serialize_order_book(symbol: str, book: OrderBook) -> Dict[str, Any]:
    """Full order book snapshot: best bid/ask plus all resting levels."""
    top = top_of_book(book)
    return {
        "symbol": symbol,
        "best_bid": top["best_bid"],
        "best_ask": top["best_ask"],
        "bids": _levels(book.bids),
        "asks": _levels(book.asks),
    }
