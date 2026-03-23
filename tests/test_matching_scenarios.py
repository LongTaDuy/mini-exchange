"""High-level matching scenarios: full, partial, no match."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestMatchingScenarios(unittest.TestCase):
    def test_full_match(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("sell-1", Side.SELL, "100", "5"))

        trades, book = engine.submit_order(limit_order("buy-1", Side.BUY, "100", "5"))

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, Decimal("100"))
        self.assertEqual(trades[0].quantity, Decimal("5"))
        self.assertEqual(book.asks, {})
        self.assertEqual(book.bids, {})

    def test_partial_match(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("sell-1", Side.SELL, "100", "10"))

        trades, book = engine.submit_order(limit_order("buy-1", Side.BUY, "100", "6"))

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal("6"))
        self.assertEqual(book.asks[Decimal("100")][0].quantity, Decimal("4"))
        self.assertEqual(book.bids, {})

    def test_no_match(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("sell-1", Side.SELL, "101", "3"))

        trades, book = engine.submit_order(limit_order("buy-1", Side.BUY, "100", "3"))

        self.assertEqual(trades, [])
        self.assertEqual(book.asks[Decimal("101")][0].quantity, Decimal("3"))
        self.assertEqual(book.bids[Decimal("100")][0].quantity, Decimal("3"))


if __name__ == "__main__":
    unittest.main()
