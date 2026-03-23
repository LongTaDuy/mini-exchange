from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Tuple

from mini_exchange.event_log import log_event
from mini_exchange.order import Order, Side
from mini_exchange.order_book import OrderBook
from mini_exchange.trade import Trade
from mini_exchange.validation import validate_limit_order


@dataclass
class MatchingEngine:
    """
    Applies limit-order matching against an OrderBook (price-time priority, partial fills).

    Owns trade id allocation; mutates incoming orders' remaining quantity in place.
    """

    book: OrderBook = field(default_factory=OrderBook)
    _next_trade_id: int = field(default=1, repr=False)

    def submit_order(
        self, order: Order, *, symbol: str | None = None
    ) -> Tuple[List[Trade], OrderBook]:
        validate_limit_order(order)
        log_event(
            "order_received",
            symbol=symbol,
            order_id=order.order_id,
            side=order.side.value,
            price=str(order.price),
            quantity=str(order.quantity),
        )
        trades: List[Trade] = []
        if order.side is Side.BUY:
            self._match_buy(order, trades)
        else:
            self._match_sell(order, trades)
        return trades, self.book

    def cancel_order(self, order_id: str, *, symbol: str | None = None) -> Order | None:
        # Cancellation only affects resting liquidity (no matching).
        if not isinstance(order_id, str) or not order_id.strip():
            return None
        canceled = self.book.cancel_order(order_id)
        if canceled is not None:
            log_event(
                "order_canceled",
                symbol=symbol,
                order_id=order_id,
                side=canceled.side.value,
                price=str(canceled.price),
                quantity=str(canceled.quantity),
            )
        return canceled

    def _alloc_trade_id(self) -> str:
        tid = f"T{self._next_trade_id}"
        self._next_trade_id += 1
        return tid

    def _match_buy(self, order: Order, trades: List[Trade]) -> None:
        while order.quantity > 0:
            best_ask = self.book.best_ask_price()
            if best_ask is None or order.price < best_ask:
                break
            self._fill_buy_against_ask_price(order, best_ask, trades)
        if order.quantity > 0:
            self.book.rest_bid(order)

    def _match_sell(self, order: Order, trades: List[Trade]) -> None:
        while order.quantity > 0:
            best_bid = self.book.best_bid_price()
            if best_bid is None or order.price > best_bid:
                break
            self._fill_sell_against_bid_price(order, best_bid, trades)
        if order.quantity > 0:
            self.book.rest_ask(order)

    def _fill_buy_against_ask_price(
        self, buy: Order, ask_price: Decimal, trades: List[Trade]
    ) -> None:
        # Partial fills: trade min(aggressor, maker); maker may stay at front with remainder.
        while buy.quantity > 0:
            maker = self.book.peek_ask(ask_price)
            if maker is None:
                break
            if maker.quantity <= 0:
                self.book.pop_ask_front(ask_price)
                continue

            qty = min(buy.quantity, maker.quantity)
            tid = self._alloc_trade_id()
            trades.append(
                Trade(
                    trade_id=tid,
                    price=ask_price,
                    quantity=qty,
                    buy_order_id=buy.order_id,
                    sell_order_id=maker.order_id,
                )
            )
            log_event(
                "trade_executed",
                trade_id=tid,
                price=str(ask_price),
                quantity=str(qty),
                buy_order_id=buy.order_id,
                sell_order_id=maker.order_id,
            )
            buy.quantity -= qty
            maker.quantity -= qty
            if maker.quantity <= 0:
                self.book.pop_ask_front(ask_price)

    def _fill_sell_against_bid_price(
        self, sell: Order, bid_price: Decimal, trades: List[Trade]
    ) -> None:
        while sell.quantity > 0:
            maker = self.book.peek_bid(bid_price)
            if maker is None:
                break
            if maker.quantity <= 0:
                self.book.pop_bid_front(bid_price)
                continue

            qty = min(sell.quantity, maker.quantity)
            tid = self._alloc_trade_id()
            trades.append(
                Trade(
                    trade_id=tid,
                    price=bid_price,
                    quantity=qty,
                    buy_order_id=maker.order_id,
                    sell_order_id=sell.order_id,
                )
            )
            log_event(
                "trade_executed",
                trade_id=tid,
                price=str(bid_price),
                quantity=str(qty),
                buy_order_id=maker.order_id,
                sell_order_id=sell.order_id,
            )
            sell.quantity -= qty
            maker.quantity -= qty
            if maker.quantity <= 0:
                self.book.pop_bid_front(bid_price)
