from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from mini_exchange.event_log import log_event
from mini_exchange.matching_engine import MatchingEngine
from mini_exchange.order import Order
from mini_exchange.order_book import OrderBook
from mini_exchange.trade import Trade


@dataclass
class Exchange:
    """
    Routes orders to an independent matcher/order book per symbol.

    Matching is guaranteed to occur within a single symbol because each symbol gets
    its own `MatchingEngine` instance with its own `OrderBook`.

    **Cross-symbol lookup:** ``get_order_any`` uses an index of resting ``order_id`` →
    symbols (maintained via ``OrderBook.on_order_removed`` and post-submit registration).
    When the same ``order_id`` rests on multiple symbols, the first match in **sorted
    symbol order** is returned (deterministic). If the index is empty (e.g. tests that
    inject engines without the normal factory), lookup falls back to a linear scan.
    """

    _engines: Dict[str, MatchingEngine] = field(default_factory=dict)
    _order_id_symbols: Dict[str, Set[str]] = field(default_factory=dict, repr=False)

    def _on_order_removed(self, symbol: str, order_id: str) -> None:
        syms = self._order_id_symbols.get(order_id)
        if not syms:
            return
        syms.discard(symbol)
        if not syms:
            del self._order_id_symbols[order_id]

    def _register_resting(self, symbol: str, order_id: str) -> None:
        self._order_id_symbols.setdefault(order_id, set()).add(symbol)

    def _get_engine(self, symbol: str) -> MatchingEngine:
        if symbol not in self._engines:
            book = OrderBook()

            def _cb(oid: str, sym: str = symbol) -> None:
                self._on_order_removed(sym, oid)

            book.on_order_removed = _cb
            self._engines[symbol] = MatchingEngine(book=book)
        return self._engines[symbol]

    def submit_order(self, symbol: str, order: Order) -> Tuple[List[Trade], OrderBook]:
        if not isinstance(symbol, str) or not symbol.strip():
            log_event(
                "validation_failure",
                source="exchange",
                reason="symbol must be a non-empty string",
            )
            raise ValueError("symbol must be a non-empty string")
        engine = self._get_engine(symbol)
        trades, book = engine.submit_order(order, symbol=symbol)
        if book.get_order(order.order_id) is not None:
            self._register_resting(symbol, order.order_id)
        return trades, book

    def get_orderbook(self, symbol: str) -> OrderBook:
        if not isinstance(symbol, str) or not symbol.strip():
            log_event(
                "validation_failure",
                source="exchange",
                reason="symbol must be a non-empty string",
            )
            raise ValueError("symbol must be a non-empty string")
        return self._get_engine(symbol).book

    def get_order(self, symbol: str, order_id: str):
        if symbol not in self._engines:
            return None
        return self._engines[symbol].book.get_order(order_id)

    def cancel_order(self, symbol: str, order_id: str) -> Optional[Order]:
        if symbol not in self._engines:
            return None
        return self._engines[symbol].cancel_order(order_id, symbol=symbol)

    def get_order_any(self, order_id: str) -> Optional[Tuple[str, Order]]:
        """
        Fetch a resting order by `order_id` across all symbols.

        Uses an O(1) index of symbols that currently hold this id when available;
        otherwise scans engines (legacy / defensive).
        """
        symbols = self._order_id_symbols.get(order_id)
        if symbols:
            for sym in sorted(symbols):
                eng = self._engines.get(sym)
                if eng is None:
                    continue
                order = eng.book.get_order(order_id)
                if order is not None:
                    return sym, order
            return None

        for sym, engine in self._engines.items():
            order = engine.book.get_order(order_id)
            if order is not None:
                return sym, order
        return None
