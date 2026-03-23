"""
Exchange wrapper for the HTTP service: forwards to the core ``Exchange`` and notifies
a ``MarketEventHub`` after mutations so WebSockets can stream trades and book tops.

The matching engine and ``mini_exchange`` package stay free of WebSocket or asyncio.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from mini_exchange import Exchange, Order, Trade
from mini_exchange.order_book import OrderBook

from mini_exchange_service.ws_hub import MarketEventHub


class NotifyingExchange(Exchange):
    """Delegates all behavior to ``Exchange`` super; emits hub events after writes."""

    def __init__(self, hub: MarketEventHub) -> None:
        super().__init__()
        self._hub = hub

    def submit_order(self, symbol: str, order: Order) -> Tuple[List[Trade], OrderBook]:
        trades, book = super().submit_order(symbol, order)
        for t in trades:
            self._hub.emit_trade(symbol, t)
        self._hub.emit_book_top(symbol, book)
        return trades, book

    def cancel_order(self, symbol: str, order_id: str) -> Optional[Order]:
        canceled = super().cancel_order(symbol, order_id)
        if canceled is not None:
            book = self.get_orderbook(symbol)
            self._hub.emit_book_top(symbol, book)
        return canceled
