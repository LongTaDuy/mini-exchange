"""Core edge cases: empty book and partial fills (see also test_matching_fifo_and_depth)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine, OrderBook, Side

from fixtures import limit_order


class TestEmptyBook(unittest.TestCase):
    def test_first_order_rests_no_trades(self) -> None:
        book = OrderBook()
        engine = MatchingEngine(book)
        trades, _ = engine.submit_order(limit_order("1", Side.BUY, "100", "5"))
        self.assertEqual(trades, [])
        self.assertEqual(len(book.bids), 1)
        self.assertEqual(book.best_bid_price(), Decimal("100"))
        self.assertIsNone(book.best_ask_price())

    def test_fully_match_then_book_empty_sides(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s", Side.SELL, "10", "3"))
        trades, book = engine.submit_order(limit_order("b", Side.BUY, "10", "3"))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal("3"))
        self.assertEqual(book.bids, {})
        self.assertEqual(book.asks, {})


class TestPartialFills(unittest.TestCase):
    def test_partial_maker_stays_at_front(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("maker", Side.SELL, "10", "10"))
        trades, _ = engine.submit_order(limit_order("agg", Side.BUY, "10", "3"))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal("3"))
        book = engine.book
        dq = book.ask_orders(Decimal("10"))
        self.assertEqual(len(dq), 1)
        self.assertEqual(dq[0].order_id, "maker")
        self.assertEqual(dq[0].quantity, Decimal("7"))

    def test_aggressor_partial_across_two_makers_then_rest(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "10", "2"))
        engine.submit_order(limit_order("s2", Side.SELL, "10", "2"))
        trades, book = engine.submit_order(limit_order("b", Side.BUY, "10", "5"))
        self.assertEqual(len(trades), 2)
        self.assertEqual([t.quantity for t in trades], [Decimal("2"), Decimal("2")])
        self.assertEqual(trades[0].sell_order_id, "s1")
        self.assertEqual(trades[1].sell_order_id, "s2")
        self.assertEqual(book.bids[Decimal("10")][0].quantity, Decimal("1"))
        self.assertEqual(book.asks, {})


if __name__ == "__main__":
    unittest.main()
