"""JSON-serializable payloads for WebSocket market data (HTTP layer only)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Dict

from mini_exchange import OrderBook, Trade


def _decimal_json(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError


def trade_event(symbol: str, trade: Trade) -> Dict[str, Any]:
    return {
        "type": "trade",
        "symbol": symbol,
        "trade": {
            "trade_id": trade.trade_id,
            "price": str(trade.price),
            "quantity": str(trade.quantity),
            "buy_order_id": trade.buy_order_id,
            "sell_order_id": trade.sell_order_id,
        },
    }


def book_top_event(symbol: str, book: OrderBook) -> Dict[str, Any]:
    bb = book.best_bid_price()
    ba = book.best_ask_price()
    bid_qty: Decimal | None = None
    ask_qty: Decimal | None = None
    if bb is not None and bb in book.bids:
        bid_qty = sum((o.quantity for o in book.bids[bb]), start=Decimal(0))
    if ba is not None and ba in book.asks:
        ask_qty = sum((o.quantity for o in book.asks[ba]), start=Decimal(0))
    return {
        "type": "book_top",
        "symbol": symbol,
        "best_bid": str(bb) if bb is not None else None,
        "best_ask": str(ba) if ba is not None else None,
        "bid_quantity": str(bid_qty) if bid_qty is not None else None,
        "ask_quantity": str(ask_qty) if ask_qty is not None else None,
    }


def dumps_event(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, default=_decimal_json, separators=(",", ":"))
