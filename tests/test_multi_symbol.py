"""Multi-symbol routing: independent books and lookups."""

from __future__ import annotations

import unittest
from decimal import Decimal

from mini_exchange import Exchange, MatchingEngine
from mini_exchange.order import Side

from fixtures import limit_order


class TestMultiSymbolIsolation(unittest.TestCase):
    def test_cross_symbol_matching_does_not_occur(self) -> None:
        exchange = Exchange()

        trades_btc, btc_book = exchange.submit_order(
            "BTC-USD", limit_order("sell-btc-1", Side.SELL, "100", "2")
        )
        self.assertEqual(trades_btc, [])

        trades_eth, eth_book = exchange.submit_order(
            "ETH-USD", limit_order("buy-eth-1", Side.BUY, "100", "2")
        )
        self.assertEqual(trades_eth, [])

        self.assertEqual(btc_book.asks[Decimal("100")][0].order_id, "sell-btc-1")
        self.assertEqual(btc_book.asks[Decimal("100")][0].quantity, Decimal("2"))
        self.assertEqual(btc_book.bids, {})

        self.assertEqual(eth_book.bids[Decimal("100")][0].order_id, "buy-eth-1")
        self.assertEqual(eth_book.bids[Decimal("100")][0].quantity, Decimal("2"))
        self.assertEqual(eth_book.asks, {})

    def test_symbols_are_independent_after_matching(self) -> None:
        exchange = Exchange()

        exchange.submit_order("BTC-USD", limit_order("sell-btc-1", Side.SELL, "100", "2"))
        exchange.submit_order("ETH-USD", limit_order("buy-eth-1", Side.BUY, "100", "2"))

        trades_btc2, btc_book2 = exchange.submit_order(
            "BTC-USD", limit_order("buy-btc-2", Side.BUY, "100", "2")
        )
        self.assertEqual(len(trades_btc2), 1)
        self.assertEqual(trades_btc2[0].quantity, Decimal("2"))

        self.assertEqual(btc_book2.asks, {})
        self.assertEqual(btc_book2.bids, {})

        eth_book = exchange.get_orderbook("ETH-USD")
        self.assertEqual(eth_book.bids[Decimal("100")][0].order_id, "buy-eth-1")
        self.assertEqual(eth_book.bids[Decimal("100")][0].quantity, Decimal("2"))
        self.assertEqual(eth_book.asks, {})

    def test_order_lookup_is_symbol_scoped(self) -> None:
        exchange = Exchange()

        exchange.submit_order("BTC-USD", limit_order("sell-btc-1", Side.SELL, "100", "2"))
        exchange.submit_order("ETH-USD", limit_order("sell-eth-1", Side.SELL, "100", "2"))

        self.assertIsNotNone(exchange.get_order("BTC-USD", "sell-btc-1"))
        self.assertIsNone(exchange.get_order("ETH-USD", "sell-btc-1"))

        exchange.submit_order("BTC-USD", limit_order("buy-btc-1", Side.BUY, "100", "2"))
        self.assertIsNone(exchange.get_order("BTC-USD", "sell-btc-1"))
        self.assertIsNotNone(exchange.get_order("ETH-USD", "sell-eth-1"))

    def test_same_order_id_allowed_on_different_symbols(self) -> None:
        ex = Exchange()
        ex.submit_order("BTC-USD", limit_order("shared-id", Side.SELL, "50", "1"))
        ex.submit_order("ETH-USD", limit_order("shared-id", Side.SELL, "50", "2"))

        btc_o = ex.get_order("BTC-USD", "shared-id")
        eth_o = ex.get_order("ETH-USD", "shared-id")
        self.assertIsNotNone(btc_o)
        self.assertIsNotNone(eth_o)
        self.assertEqual(btc_o.quantity, Decimal("1"))
        self.assertEqual(eth_o.quantity, Decimal("2"))

        ex.submit_order("BTC-USD", limit_order("buy-btc", Side.BUY, "50", "1"))
        self.assertIsNone(ex.get_order("BTC-USD", "shared-id"))
        self.assertIsNotNone(ex.get_order("ETH-USD", "shared-id"))

    def test_three_symbols_no_cross_matching(self) -> None:
        ex = Exchange()
        for sym in ("BTC-USD", "ETH-USD", "SOL-USD"):
            ex.submit_order(sym, limit_order(f"s-{sym}", Side.SELL, "10", "1"))

        trades, sol_book = ex.submit_order(
            "SOL-USD", limit_order("b-sol", Side.BUY, "10", "1")
        )
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].sell_order_id, "s-SOL-USD")
        self.assertEqual(sol_book.asks, {})

        btc_book = ex.get_orderbook("BTC-USD")
        eth_book = ex.get_orderbook("ETH-USD")
        self.assertIn(Decimal("10"), btc_book.asks)
        self.assertIn(Decimal("10"), eth_book.asks)


class TestSingleSymbolEngineStillIndependent(unittest.TestCase):
    """MatchingEngine has one book; sanity check unrelated to Exchange."""

    def test_two_engines_do_not_share_liquidity(self) -> None:
        a = MatchingEngine()
        b = MatchingEngine()
        a.submit_order(limit_order("s1", Side.SELL, "1", "1"))
        trades, _ = b.submit_order(limit_order("b1", Side.BUY, "1", "1"))
        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
