"""Invalid inputs: order validation, exchange routing, duplicate resting ids."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import Exchange, InvalidOrderError, MatchingEngine
from mini_exchange.order import Order, Side

from fixtures import limit_order


class TestOrderValidation(unittest.TestCase):
    def test_empty_order_id(self) -> None:
        with self.assertRaises(InvalidOrderError):
            Order("  ", Side.BUY, Decimal("1"), Decimal("1"))

    def test_non_positive_quantity(self) -> None:
        with self.assertRaises(InvalidOrderError):
            Order("a", Side.BUY, Decimal("1"), Decimal("0"))

    def test_non_positive_price(self) -> None:
        with self.assertRaises(InvalidOrderError):
            Order("a", Side.BUY, Decimal("0"), Decimal("1"))

    def test_nan_price(self) -> None:
        with self.assertRaises(InvalidOrderError):
            Order("a", Side.BUY, Decimal("NaN"), Decimal("1"))

    def test_submit_rejects_mutated_order(self) -> None:
        order = limit_order("x", Side.BUY, "10", "1")
        order.quantity = Decimal("0")
        engine = MatchingEngine()
        with self.assertRaises(InvalidOrderError):
            engine.submit_order(order)


class TestExchangeInvalidSymbol(unittest.TestCase):
    def test_submit_rejects_empty_symbol(self) -> None:
        ex = Exchange()
        with self.assertRaises(ValueError):
            ex.submit_order(
                "   ",
                limit_order("a", Side.BUY, "1", "1"),
            )

    def test_get_orderbook_rejects_empty_symbol(self) -> None:
        ex = Exchange()
        with self.assertRaises(ValueError):
            ex.get_orderbook("")


class TestDuplicateRestingOrderId(unittest.TestCase):
    def test_second_rest_same_order_id_raises(self) -> None:
        engine = MatchingEngine()
        engine.submit_order(limit_order("dup", Side.SELL, "10", "1"))
        with self.assertRaises(ValueError):
            engine.submit_order(limit_order("dup", Side.SELL, "10", "1"))


if __name__ == "__main__":
    unittest.main()
