"""Matching depth: same price level, FIFO, partial fills across multiple makers."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestMultipleOrdersSamePrice(unittest.TestCase):
    def test_three_sells_rest_in_one_level(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "1"))
        engine.submit_order(limit_order("s2", Side.SELL, "100", "2"))
        engine.submit_order(limit_order("s3", Side.SELL, "100", "3"))

        level = engine.book.ask_orders(Decimal("100"))
        self.assertEqual([o.order_id for o in level], ["s1", "s2", "s3"])

    def test_three_buys_rest_in_one_level(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("b1", Side.BUY, "50", "1"))
        engine.submit_order(limit_order("b2", Side.BUY, "50", "2"))
        engine.submit_order(limit_order("b3", Side.BUY, "50", "3"))

        level = engine.book.bid_orders(Decimal("50"))
        self.assertEqual([o.order_id for o in level], ["b1", "b2", "b3"])


class TestFifoWithinPrice(unittest.TestCase):
    def test_buy_consumes_oldest_sell_first(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "2"))
        engine.submit_order(limit_order("s2", Side.SELL, "100", "5"))

        trades, _ = engine.submit_order(limit_order("b1", Side.BUY, "100", "2"))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].sell_order_id, "s1")
        self.assertEqual(trades[0].quantity, Decimal("2"))

        front = engine.book.peek_ask(Decimal("100"))
        self.assertIsNotNone(front)
        self.assertEqual(front.order_id, "s2")

    def test_sell_consumes_oldest_buy_first(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("b1", Side.BUY, "100", "3"))
        engine.submit_order(limit_order("b2", Side.BUY, "100", "4"))

        trades, _ = engine.submit_order(limit_order("s1", Side.SELL, "100", "3"))
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].buy_order_id, "b1")

        front = engine.book.peek_bid(Decimal("100"))
        self.assertIsNotNone(front)
        self.assertEqual(front.order_id, "b2")


class TestPartialFillAcrossMultipleMakers(unittest.TestCase):
    def test_buy_sweeps_two_full_and_partial_third(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "10", "2"))
        engine.submit_order(limit_order("s2", Side.SELL, "10", "2"))
        engine.submit_order(limit_order("s3", Side.SELL, "10", "4"))

        trades, book = engine.submit_order(limit_order("b1", Side.BUY, "10", "7"))
        self.assertEqual(len(trades), 3)
        self.assertEqual(
            [(t.sell_order_id, t.quantity) for t in trades],
            [
                ("s1", Decimal("2")),
                ("s2", Decimal("2")),
                ("s3", Decimal("3")),
            ],
        )

        remaining = book.ask_orders(Decimal("10"))
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].order_id, "s3")
        self.assertEqual(remaining[0].quantity, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
