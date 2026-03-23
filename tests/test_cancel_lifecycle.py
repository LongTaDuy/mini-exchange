"""Cancel workflows: cancel resting liquidity then place again."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestCancelThenReplace(unittest.TestCase):
    def test_cancel_removes_order_then_same_id_can_rest_again(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("x", Side.SELL, "50", "10"))
        self.assertIsNotNone(engine.book.get_order("x"))

        canceled = engine.cancel_order("x")
        self.assertIsNotNone(canceled)
        self.assertEqual(canceled.quantity, Decimal("10"))
        self.assertIsNone(engine.book.get_order("x"))

        engine.submit_order(limit_order("x", Side.SELL, "50", "2"))
        again = engine.book.get_order("x")
        self.assertIsNotNone(again)
        self.assertEqual(again.quantity, Decimal("2"))

    def test_cancel_one_maker_second_remains_at_same_price(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "1"))
        engine.submit_order(limit_order("s2", Side.SELL, "100", "2"))

        engine.cancel_order("s1")
        self.assertIsNone(engine.book.get_order("s1"))
        self.assertIsNotNone(engine.book.get_order("s2"))

        level = engine.book.ask_orders(Decimal("100"))
        self.assertEqual([o.order_id for o in level], ["s2"])


if __name__ == "__main__":
    unittest.main()
