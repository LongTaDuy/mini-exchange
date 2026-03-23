"""Cancel resting orders (core engine)."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestCancel(unittest.TestCase):
    def test_cancel_resting_order_removes_from_book(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "5"))

        canceled = engine.cancel_order("s1")
        self.assertIsNotNone(canceled)
        self.assertEqual(canceled.quantity, Decimal("5"))

        self.assertIsNone(engine.book.get_order("s1"))
        self.assertEqual(engine.book.asks, {})

    def test_cancel_nonexistent_order_is_noop(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "5"))

        canceled = engine.cancel_order("does-not-exist")
        self.assertIsNone(canceled)

        self.assertIsNotNone(engine.book.get_order("s1"))
        self.assertEqual(engine.book.asks[Decimal("100")][0].order_id, "s1")

    def test_cancel_partial_remaining_order(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "10"))

        engine.submit_order(limit_order("b1", Side.BUY, "100", "6"))
        maker = engine.book.get_order("s1")
        self.assertIsNotNone(maker)
        self.assertEqual(maker.quantity, Decimal("4"))

        canceled = engine.cancel_order("s1")
        self.assertIsNotNone(canceled)
        self.assertEqual(canceled.quantity, Decimal("4"))
        self.assertIsNone(engine.book.get_order("s1"))
        self.assertEqual(engine.book.asks, {})


if __name__ == "__main__":
    unittest.main()
