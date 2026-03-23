"""WebSocket market stream (requires create_app() default with NotifyingExchange + hub)."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from mini_exchange_service.main import create_app


class TestWebSocketMarketStream(unittest.TestCase):
    def test_subscribe_then_trade_and_book_top_events(self) -> None:
        app = create_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                ws.send_json({"action": "subscribe", "symbols": ["BTC-USD"]})
                self.assertEqual(ws.receive_json()["type"], "subscribed")
                self.assertEqual(ws.receive_json()["type"], "book_top")

                client.post(
                    "/orders",
                    json={
                        "symbol": "BTC-USD",
                        "order_id": "s1",
                        "side": "sell",
                        "price": "100",
                        "quantity": "5",
                        "timestamp": 0,
                    },
                )
                self.assertEqual(ws.receive_json()["type"], "book_top")

                client.post(
                    "/orders",
                    json={
                        "symbol": "BTC-USD",
                        "order_id": "b1",
                        "side": "buy",
                        "price": "100",
                        "quantity": "3",
                        "timestamp": 0,
                    },
                )
                t = ws.receive_json()
                self.assertEqual(t["type"], "trade")
                self.assertEqual(t["symbol"], "BTC-USD")
                self.assertEqual(t["trade"]["quantity"], "3")
                b = ws.receive_json()
                self.assertEqual(b["type"], "book_top")
                self.assertEqual(b["symbol"], "BTC-USD")

    def test_plain_exchange_has_no_ws_hub(self) -> None:
        from mini_exchange import Exchange

        app = create_app(Exchange())
        self.assertIsNone(app.state.hub)
        paths = [getattr(r, "path", "") for r in app.routes]
        self.assertNotIn("/ws", paths)


if __name__ == "__main__":
    unittest.main()
