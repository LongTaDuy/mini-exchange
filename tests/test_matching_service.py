"""Tests for the Matching Service (services/matching-service).

The service exposes its FastAPI app as the top-level package `app`. Because the
gateway uses the same package name, we load this service in isolation (purge any
cached `app*` modules, then import with the service dir at the front of
sys.path) and drive it with FastAPI's TestClient.
"""

from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
MATCHING_DIR = REPO_ROOT / "services" / "matching-service"


def _load_matching():
    for name in [m for m in list(sys.modules) if m == "app" or m.startswith("app.")]:
        del sys.modules[name]
    path = str(MATCHING_DIR)
    if path in sys.path:
        sys.path.remove(path)
    sys.path.insert(0, path)
    main = importlib.import_module("app.main")
    deps = importlib.import_module("app.dependencies")
    return main, deps


_main, _deps = _load_matching()

SELL = {
    "symbol": "BTC-USD",
    "order_id": "s1",
    "side": "sell",
    "price": "100",
    "quantity": "5",
}
BUY = {
    "symbol": "BTC-USD",
    "order_id": "b1",
    "side": "buy",
    "price": "100",
    "quantity": "3",
}


class TestMatchingService(unittest.TestCase):
    def setUp(self) -> None:
        # Fresh singleton Exchange per test for isolation.
        _deps._exchange_singleton.cache_clear()
        self.client = TestClient(_main.app)

    def test_health(self) -> None:
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "service": "matching"})

    def test_submit_resting_buy_order(self) -> None:
        buy = {**BUY, "quantity": "3"}
        r = self.client.post("/orders", json=buy)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["symbol"], "BTC-USD")
        self.assertEqual(body["order"]["order_id"], "b1")
        self.assertTrue(body["order"]["resting"])
        self.assertEqual(body["order"]["quantity_remaining"], "3")
        self.assertEqual(body["trades"], [])
        self.assertEqual(body["book"]["best_bid"], "100")
        self.assertIsNone(body["book"]["best_ask"])

    def test_submit_crossing_sell_returns_trade(self) -> None:
        # Rest a buy, then cross it with a sell.
        self.client.post("/orders", json=BUY)
        sell = {**SELL, "order_id": "s2", "quantity": "3"}
        r = self.client.post("/orders", json=sell)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(len(body["trades"]), 1)
        trade = body["trades"][0]
        self.assertEqual(trade["price"], "100")
        self.assertEqual(trade["quantity"], "3")
        self.assertEqual(trade["buy_order_id"], "b1")
        self.assertEqual(trade["sell_order_id"], "s2")
        self.assertEqual(body["order"]["quantity_remaining"], "0")
        self.assertFalse(body["order"]["resting"])

    def test_cancel_order(self) -> None:
        self.client.post("/orders", json=SELL)
        r = self.client.post(
            "/orders/cancel", json={"symbol": "BTC-USD", "order_id": "s1"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["canceled"])
        self.assertEqual(body["canceled_quantity"], "5")
        self.assertIsNone(body["book"]["best_ask"])
        # Order no longer resting.
        self.assertEqual(self.client.get("/orders/s1").status_code, 404)

    def test_get_order_book(self) -> None:
        self.client.post("/orders", json=SELL)
        r = self.client.get("/orderbook/BTC-USD")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["symbol"], "BTC-USD")
        self.assertEqual(body["best_ask"], "100")
        self.assertIsNone(body["best_bid"])
        self.assertEqual(body["bids"], [])
        self.assertEqual(len(body["asks"]), 1)
        self.assertEqual(body["asks"][0]["price"], "100")
        self.assertEqual(body["asks"][0]["orders"][0]["order_id"], "s1")
        self.assertEqual(body["asks"][0]["orders"][0]["quantity"], "5")

    def test_get_order_by_id(self) -> None:
        self.client.post("/orders", json=SELL)
        r = self.client.get("/orders/s1")
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["symbol"], "BTC-USD")
        self.assertEqual(body["order"]["order_id"], "s1")
        self.assertEqual(body["order"]["side"], "sell")
        self.assertEqual(body["order"]["price"], "100")
        self.assertEqual(body["order"]["quantity"], "5")

    def test_get_missing_order_returns_404(self) -> None:
        r = self.client.get("/orders/does-not-exist")
        self.assertEqual(r.status_code, 404)

    def test_invalid_quantity_returns_400(self) -> None:
        r = self.client.post("/orders", json={**BUY, "quantity": "0"})
        self.assertEqual(r.status_code, 400, r.text)


if __name__ == "__main__":
    unittest.main()
