"""Order book lookup by order_id after match / rest."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestOrderLookup(unittest.TestCase):
    def test_full_match_orders_removed_from_lookup(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "5"))

        trades, book = engine.submit_order(limit_order("b1", Side.BUY, "100", "5"))

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal("5"))
        self.assertEqual(book.bids, {})
        self.assertEqual(book.asks, {})
        self.assertIsNone(book.get_order("s1"))
        self.assertIsNone(book.get_order("b1"))

    def test_partial_match_maker_stays_in_lookup(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "100", "10"))

        trades, book = engine.submit_order(limit_order("b1", Side.BUY, "100", "6"))

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal("6"))

        s1 = book.get_order("s1")
        self.assertIsNotNone(s1)
        self.assertEqual(s1.quantity, Decimal("4"))
        self.assertIsNone(book.get_order("b1"))

    def test_no_match_aggressor_rests_and_is_lookupable(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("s1", Side.SELL, "101", "3"))

        trades, book = engine.submit_order(limit_order("b1", Side.BUY, "100", "3"))

        self.assertEqual(trades, [])

        s1 = book.get_order("s1")
        self.assertIsNotNone(s1)
        self.assertEqual(s1.quantity, Decimal("3"))

        b1 = book.get_order("b1")
        self.assertIsNotNone(b1)
        self.assertEqual(b1.quantity, Decimal("3"))


if __name__ == "__main__":
    unittest.main()
