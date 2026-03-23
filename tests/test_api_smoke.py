import unittest

from fastapi.testclient import TestClient

from mini_exchange import Exchange
from mini_exchange_service.main import create_app


class TestApiSmoke(unittest.TestCase):
    def test_place_order_and_no_match_rests(self) -> None:
        client = TestClient(create_app(Exchange()))

        r = client.post(
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
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["symbol"], "BTC-USD")
        self.assertEqual(body["order"]["order_id"], "s1")
        self.assertEqual(body["order"]["quantity_submitted"], "5")
        self.assertEqual(body["order"]["quantity_remaining"], "5")
        self.assertTrue(body["order"]["resting"])
        self.assertEqual(body["trades"], [])
        self.assertIsNone(body["book"]["best_bid"])
        self.assertEqual(body["book"]["best_ask"], "100")

    def test_place_order_match_produces_trade(self) -> None:
        client = TestClient(create_app(Exchange()))

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

        r = client.post(
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
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["trades"]), 1)
        self.assertEqual(body["trades"][0]["quantity"], "3")
        self.assertEqual(body["trades"][0]["price"], "100")
        self.assertEqual(body["order"]["quantity_remaining"], "0")
        self.assertFalse(body["order"]["resting"])

    def test_cancel_removes_order_from_lookup(self) -> None:
        client = TestClient(create_app(Exchange()))

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

        r = client.post(
            "/orders/cancel",
            json={"symbol": "BTC-USD", "order_id": "s1"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["canceled"])
        self.assertEqual(body["canceled_quantity"], "5")
        self.assertIsNone(body["book"]["best_bid"])
        self.assertIsNone(body["book"]["best_ask"])

        r2 = client.get("/orders/s1")
        self.assertEqual(r2.status_code, 404)
        err = r2.json()
        self.assertFalse(err["success"])
        self.assertEqual(err["error"]["code"], "not_found")

    def test_validation_error_shape(self) -> None:
        client = TestClient(create_app(Exchange()))
        r = client.post(
            "/orders",
            json={
                "symbol": "BTC-USD",
                "order_id": "x",
                "side": "buy",
                # missing price + quantity triggers RequestValidationError (422)
            },
        )
        self.assertEqual(r.status_code, 422, r.text)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "validation_error")
        self.assertIn("details", body["error"])
        self.assertTrue(len(body["error"]["details"]) >= 1)

    def test_invalid_order_error_shape(self) -> None:
        client = TestClient(create_app(Exchange()))
        r = client.post(
            "/orders",
            json={
                "symbol": "BTC-USD",
                "order_id": "x",
                "side": "buy",
                "price": "1",
                "quantity": "0",
            },
        )
        self.assertEqual(r.status_code, 400, r.text)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "invalid_order")

    def test_duplicate_resting_order_id_returns_bad_request(self) -> None:
        client = TestClient(create_app(Exchange()))
        payload = {
            "symbol": "BTC-USD",
            "order_id": "dup",
            "side": "sell",
            "price": "10",
            "quantity": "1",
            "timestamp": 0,
        }
        self.assertEqual(client.post("/orders", json=payload).status_code, 200)
        r2 = client.post("/orders", json=payload)
        self.assertEqual(r2.status_code, 400, r2.text)
        body = r2.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "bad_request")


if __name__ == "__main__":
    unittest.main()
